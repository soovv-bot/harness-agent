# SearchHarness_0425 强化分析

> 对标 Codex / GPT Researcher / Open Deep Research 等主流 harness agent，针对 BrowseComp 单一领域（多跳事实型问答），识别当前项目最实用的强化方向。
> 日期：2026-08-04

---

## 评估基准与方法论定位

BrowseComp 的本质：**长尾、多跳、需要精确证据的事实型问答**。问题设计为"难以靠单次搜索命中"，需要 agent 进行多步推理 + 证据收集 + 候选筛选。这与通用 QA（SimpleQA/HotpotQA）的区别在于：
- 答案实体**不在训练数据中**（必须联网）
- 单次搜索**几乎不可能命中**（需多跳）
- 答案**唯一**但**难以枚举**（需收敛验证）

当前项目已具备的核心能力（相比 OffSeeker 原版）：
- ✅ 三阶段流水线（candidate_generation → candidate_verification → final_check）
- ✅ 结构化候选状态（hard_conflicts / verification_status）
- ✅ QueryCritic 反重复 + SubtaskCritic 反方向
- ✅ 增强轨迹录制（10 字段，可用于蒸馏）
- ✅ 并发安全 + best-effort 终结

---

## 1. 搜索结果处理：返回给模型的内容质量（最高 ROI）

### 问题诊断

当前 `search_tools.py` 的 `search()` 返回 Serper 原始 JSON，经 `visit_urls` 用 Jina/html2text 抓取后，再由 LLM `call_llm` 做一次**粗粒度提取**（`EXTRACTOR_PROMPT_TEMPLATE`）。但存在三个关键缺陷：

**A. search 结果无去噪与重排**
当前 `search()` 把 Serper 的 `organic` 结果（title + snippet + url）直接 dump 给模型。模型看到的是 10 条混杂结果，没有按"与问题的相关性"重排，也没有按"来源权威性"加权。BrowseComp 的长尾问题下，Serper 前 3 条往往是 Wikipedia/通用页面（高 SEO 但低信息密度），真正有用的结果在第 5-8 条。

**B. visit_urls 抓取无 query-aware 截断**
`visit_urls` 抓取整页后用 LLM 提取，但截断策略是**按 token 数硬截断**（`VISIT_URLS_RAW_RETURN_MAX_TOKENS=4000`），而非按 query 相关性保留段落。长页面（Wikipedia 全文、PDF）的关键证据可能在第 3000 token 处，被截断丢失。

**C. 无证据级抽取**
当前抽取是"整页 → 一段报告"。但 BrowseComp 需要的是**特定事实**（如"Achimota School 成立于 1924 年"），而非整页摘要。模型拿到的是二次加工的段落，丢失了原始的句子级证据，导致后续验证无法引用精确来源。

### 实用强化方案

**方案 1A：search 结果结构化 + 去重**（1-2 天）
```python
# search_tools.py: search() 返回时做后处理
def _postprocess_serper_results(raw: dict, query: str) -> list:
    """按来源权威性 + 查询相关性重排，去重同源结果。"""
    organic = raw.get("organic", [])
    # 1. 去重：相同域名只保留第一条（除非 query 含站点名）
    seen_domains = set()
    deduped = []
    for r in organic:
        domain = urlparse(r["link"]).netloc
        if domain in seen_domains and domain not in {"wikipedia.org", "britannica.com"}:
            continue
        seen_domains.add(domain)
        deduped.append(r)
    # 2. 权威性加权：百科/官方 > 新闻 > 博客
    authority = {"wikipedia.org": 3, "britannica.com": 3, ".gov": 3, ".edu": 2}
    def authority_score(r):
        d = urlparse(r["link"]).netloc
        return next((v for k, v in authority.items() if k in d), 1)
    deduped.sort(key=lambda r: -authority_score(r))
    # 3. 截断到 top 8（减少 token 占用）
    return deduped[:8]
```

**方案 1B：query-aware 段落级抽取**（2-3 天）
替换 `visit_urls` 的"整页 LLM 提取"为"段落切分 → 按相关性保留 → 结构化证据条目"：
```python
def _extract_evidence_segments(html: str, query: str) -> list[dict]:
    """切分为段落，按 query 相关性打分，返回 top-K 证据段。"""
    paragraphs = _split_paragraphs(html)  # 按 <p> / 换行切分
    scored = [(p, _relevance_score(p, query)) for p in paragraphs]
    scored.sort(key=lambda x: -x[1])
    return [{"text": p, "score": s, "char_offset": offset} for p, s in scored[:5]]
```
这样模型拿到的是**原始句子级证据**（可引用、可验证），而非 LLM 二次加工的摘要。

---

## 2. 验证阶段：候选验证的"证据锚定"缺失（次高 ROI）

### 问题诊断

当前 `candidate_verification` 阶段：从 `verification_queue` 取候选 → planner 生成验证子任务 → executor 搜索 → findings 更新候选状态。但验证逻辑有两个缺陷：

**A. 验证子任务无证据锚定**
planner 生成的验证子任务是"验证候选 X 是否满足约束 Y"，但没有要求 executor **引用具体证据**。executor 返回的 findings 里 `evidence` 字段是自由文本，没有强制要求"来源 URL + 原文句子"。这导致：
- 模型可能基于**记忆**而非**搜索结果**判断（幻觉）
- 蒸馏训练时，模型学不到"如何从证据推导结论"
- 失败排查时无法定位"哪条证据支撑/推翻了哪个候选"

**B. 硬冲突判定无量化阈值**
`SearchStateStore` 的 `hard_conflicts` 是 executor 自由填写的字符串列表，没有量化标准。两个候选都"声称"满足同一约束时，是否构成硬冲突完全靠模型主观判断。BrowseComp 的失败案例中，大量错误源于"伪硬冲突"（模型把不相关的约束误判为冲突）或"漏报硬冲突"（真正冲突未被识别）。

### 实用强化方案

**方案 2A：证据锚定的 findings schema**（1-2 天）
修改 `_extract_findings` 强制要求每条 `candidate_assessment` 带 `evidence` 数组，每条证据含 `source_url` + `quote`（原文片段）+ `constraint_matched`：
```json
{
  "candidate_updates": {
    "candidate_assessments": [
      {
        "name": "Achimota School",
        "verification_status": "verified",
        "evidence": [
          {"source_url": "https://en.wikipedia.org/wiki/Achimota_School",
           "quote": "Founded in 1924 by the British colonial government",
           "constraint_matched": "founded_in_1920s"}
        ]
      }
    ]
  }
}
```
在 `_coerce_findings` 中校验：`verification_status == "verified"` 必须有 ≥1 条 `evidence` 带 `source_url`。无证据的"verified"降级为"partial"。

**方案 2B：约束级冲突矩阵**（2-3 天）
在 `SearchStateStore` 增加 `_conflict_matrix: Dict[str, Dict[str, bool]]`（约束 × 候选 → 是否满足），验证阶段更新此矩阵。硬冲突判定改为"同一约束下 ≥2 候选 claim 满足且都有证据"，而非自由文本。finalizer 收敛时检查矩阵：若任一约束有冲突，不收敛。

---

## 3. Planner 决策：缺乏"反思驱动"的重规划（中 ROI）

### 问题诊断

当前 planner 的重规划依赖 SubtaskCritic 的 reject/pivot 信号，但这是**被动式**的（critic 判定后才改）。对比 Codex / GPT Researcher 的做法：每轮迭代后让 planner **主动反思**——"上一轮找到了什么、还缺什么、下一步该往哪走"。

当前 planner 每轮收到的 `compact_state` 是候选列表 + 已搜索查询摘要，但**没有结构化的"差距分析"**。planner 看到的是"已找到 3 个候选"，但不知道"还差几个约束未验证"。

### 实用强化方案

**方案 3A：迭代后注入"差距摘要"**（1 天）
在 `record_planner` 调用前，注入一段结构化的"上一轮差距"到 planner 上下文：
```python
def _build_gap_summary(self, iteration: int) -> str:
    records = self._all_candidate_records()
    unverified = [r for r in records if r.get("verification_status") == "unverified"]
    partial = [r for r in records if r.get("verification_status") == "partial"]
    unresolved_constraints = set()
    for r in records:
        unresolved_constraints.update(r.get("unresolved_constraints", []))
    return (
        f"[Iteration {iteration} gap] "
        f"unverified={len(unverified)}, partial={len(partial)}, "
        f"unresolved_constraints={list(unresolved_constraints)[:5]}. "
        f"Next subtask MUST target an unresolved constraint."
    )
```
注入到 planner 的 `compact_state` 或作为独立 user message。这让 planner 从"盲目发子任务"变为"针对缺口发子任务"。

---

## 4. 轨迹蒸馏质量：思考过程与决策依据的捕获（中 ROI，但决定训练效果）

### 问题诊断

增强轨迹已记录 events/search_log/llm_calls，但**对蒸馏最关键的"决策推理"仍是黑箱**。当前 planner/executor 的 `reasoning_content`（GLM-5.2 的思考链）被 `llm_reasoning_compat.py` 捕获但**未写入轨迹的 llm_calls**。derive 方法只统计了 `reasoning_chars` 数量，没有保存思考内容。

蒸馏训练需要的是：模型看到"搜索结果 A → 思考为什么排除候选 X → 决定搜索 B"。如果思考链丢失，蒸馏出的模型只会模仿"搜索行为序列"而不知"为何这么搜"。

### 实用强化方案

**方案 4A：在 llm_calls 中保存 reasoning_content**（0.5 天）
修改 `_derive_llm_calls_from_conversations`，从 executor/planner 的 assistant message 中提取 `reasoning_content` 字段（已在 `assistant_message_to_dict` 中保留），存入 `llm_calls[i].reasoning_text`：
```python
def _derive_llm_calls_from_conversations(self):
    for turn in self._planner_turns + self._executor_turns:
        for msg in turn["messages"]:
            if msg.get("role") == "assistant":
                reasoning = msg.get("reasoning_content", "")
                if reasoning:
                    calls.append({
                        ...,
                        "reasoning_text": reasoning[:2000],  # 截断防爆
                        "reasoning_chars": len(reasoning),
                    })
```

**方案 4B：决策点标注**（1 天）
在 events 流中，对每个 `candidate_change` 事件补充 `decision_rationale` 字段——从该轮 executor 的 reasoning_content 中提取与候选相关的句子。这让蒸馏数据带"为什么 add/eliminate 这个候选"的标注。

---

## 5. Grader 鲁棒性：单一 LLM 判定的脆弱性（低 ROI 但影响评估可信度）

### 问题诊断

当前 `LLMGrader` 用单个 LLM 调用判定 `correct: true/false`。BrowseComp 答案是精确实体，但 grader prompt 允许"tolerate minor differences"。实测发现：
- 大小写/别名差异：grader 有时判 false（如 "Achimota School" vs "Achimota school"）
- 多实体答案：grader 倾向于只比对第一个实体

### 实用强化方案

**方案 5A：归一化 + 多次判定投票**（0.5 天）
- 归一化：对 `extracted` 和 `correct_answer` 做 `strip().lower().remove_punctuation()` 后再比对，只有归一化后仍不等才调 LLM
- 投票：对边界 case（LLM 判 false 但归一化相等，或反之），调 3 次 LLM 取多数票

---

## 优先级排序与实施建议

| 优先级 | 方案 | 预估工期 | 预期收益 |
|--------|------|---------|---------|
| **P0** | 1A search 结果结构化去噪 | 1-2 天 | 提升单次搜索命中率，减少无效抓取 |
| **P0** | 2A 证据锚定 findings schema | 1-2 天 | 消除幻觉，验证可追溯 |
| **P1** | 4A 保存 reasoning_content 到轨迹 | 0.5 天 | 蒸馏质量大幅提升 |
| **P1** | 1B query-aware 段落级抽取 | 2-3 天 | 长页面证据不丢失 |
| **P1** | 3A 迭代后差距摘要注入 | 1 天 | planner 从盲目→定向 |
| **P2** | 2B 约束级冲突矩阵 | 2-3 天 | 硬冲突判定可量化 |
| **P2** | 4B 决策点标注 | 1 天 | 蒸馏带"为什么" |
| **P3** | 5A grader 归一化+投票 | 0.5 天 | 评估更可信 |

**建议实施顺序**：先做 1A + 2A（搜索质量 + 证据锚定）跑一轮看准确率变化，再做 4A（轨迹 reasoning）确认蒸馏数据可用，最后做 1B + 3A 优化深度。

---

## 与主流框架的差距总结

| 维度 | 当前项目 | Codex/GPT Researcher | 差距 |
|------|---------|---------------------|------|
| 搜索结果处理 | 原始 JSON dump | 结果重排 + 去噪 + 段落级抽取 | **大** |
| 证据锚定 | 自由文本 evidence | 句子级 quote + source_url | **大** |
| 重规划触发 | 被动（critic reject） | 主动（每轮反思 + 差距分析） | 中 |
| 候选冲突判定 | 自由文本 hard_conflicts | 约束级矩阵 + 量化阈值 | 中 |
| 思考链捕获 | reasoning_chars 计数 | reasoning_content 全文 | **大**（蒸馏关键） |
| 上下文管理 | micro compact（保留最近 3 条 tool） | 分段摘要 + 检索增强 | 中 |
| 工具调用 | 串行/并行混合 | 全并行 + 依赖感知调度 | 小 |

> 核心判断：当前项目在**架构**（三阶段流水线、候选状态、轨迹录制）上已接近主流框架，但在**数据质量细节**（搜索结果处理、证据锚定、思考链捕获）上有明显差距。这些细节决定了 BrowseComp 准确率和蒸馏效果，应优先补齐。
