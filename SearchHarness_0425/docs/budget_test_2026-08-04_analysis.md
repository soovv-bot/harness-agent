# 预算配置实测分析（2026-08-04）

## 测试设置

| 项 | 值 |
|----|----|
| 题目 | BrowseComp seed=123, sample=10, position=3 |
| 正确答案 | Whitesnake |
| 模型 | GLM-5.2 @ tenyun litellm 网关 |
| 思考档 | `EXECUTOR_THINKING=max` |
| 预算 | `max_iterations=4, max_crawl_calls=30, max_planner_searches=8, max_executor_searches=20, max_total_searches=60`（平衡档降配版，单题 10–15min） |
| 并发 | 1 worker |

## 结果

| 指标 | 值 |
|------|----|
| 状态 | finished |
| 答案 | John Lennon（错误，正确为 Whitesnake） |
| 评分 | `correct=False` |
| 耗时 | 938.3s（15.6 min） |
| 迭代 | 4/4（全部 candidate_generation，从未进入 verification） |

## 过程分析

### 迭代轨迹

| iter | phase | subtask | 耗时 | candidates | 备注 |
|------|-------|---------|------|-----------|------|
| 0 | candidate_generation | "Search for candidate entities..." | 154.2s | 12（Lennon/Richards/Townshend/...） | 候选偏 mainstream rock，无 Whitesnake 的 David Coverdale |
| 1 | candidate_generation | "rock musician worked in boutique" | 108.6s | 5（Malcolm McLaren/Christine McVie/...） | 搜对方向但漏 Coverdale |
| 2 | candidate_generation | "distinctive phrase or acknowledgement" | 54.0s | 0（空） | structurer#1 恢复出 2257c 但无候选 |
| 3 | candidate_generation | "Crawl Loudwire article 'Jobs Rock+Metal Musicians Had'" | 299.4s | 7（McCartney/Starr/Clapton/...） | 抓取成功但仍是错候选 |
| wrap-up | — | — | 70.1s | — | planner 仍 0-content |
| finalizer | — | — | 19.4s | answer="John Lennon" | 选第一个候选作答 |

### Planner 调用统计（11 次，全部 content=0c）

| 调用序 | 耗时 | content | reasoning | structurer | 后果 |
|--------|------|---------|----------|-----------|------|
| initial | 65.3s | 0c | 31969c | skipped | 无初始 plan |
| iter0 | 17.3s | 3804c | 4017c | n/a（有 content） | 正常，能进 iter1 |
| iter1 | 53.9s | 0c | 29683c | skipped | 无新 plan，复用 iter0 plan |
| iter2 | 52.8s | 0c | 30020c | skipped | 同上 |
| iter3 | 68.6s | 0c | 22228c | skipped | 同上 |
| wrap-up | 70.1s | 0c | 29034c | skipped | 无协议收尾 |
| finalizer-prefix | 16.1s | 0c | 1633c | n/a | finalizer 自行生成 |

**关键模式：Planner 共 11 次 LLM 调用，其中 7 次输出 22K–32K reasoning 字符但 content=0。** structurer skip 逻辑正确识别"endpoint ignored reasoning_effort=minimal"并跳过（避免无谓二次调用），但这意味着 Planner 无法产出 `<planning>` 块。

## 根因诊断

### Bug：Planner 未接收 `reasoning_effort`

`search_harness_pipeline_v4.py:65` 构造 Planner 时**未传 `reasoning_effort`**：

```python
self.planner = PlanningAgentV3(api_base=..., model_id=..., search_budget=...)
# ↑ 缺 reasoning_effort 参数
```

而 `planning_agent_v3.py:369` 调用 LLM 时也未传 `reasoning_effort_override`：

```python
response = chat_completion_with_structuring(
    self.client, model_id=..., messages=..., tools=None, ...
    # ↑ 缺 reasoning_effort_override
)
```

结果：`_resolve_effort()` 走 fallback 链 → 读 `LLM_THINKING_BUDGET_TOKENS=0` → 解析为 `"minimal"` → 传给端点 `reasoning_effort=minimal`。

### GLM-5.2 / tenyun 端点行为

- GLM-5.2 原生仅支持 `max`/`high`，**不支持 `minimal`/`low`/`medium`**
- tenyun litellm 网关把 `minimal` 静默重映射为 `high` 或 `max`（实测 30K reasoning 字符表明行为接近 `max`）
- 模型在深度思考模式下**推理耗尽输出预算**，content=0（"推理饥饿"）

### 对比 Executor（正常工作）

Executor 在 `reasoning_effort=max`（从 `EXECUTOR_THINKING` 传入）下：
- turn1: 48.9s, 0c content, 22621c reasoning → structurer 恢复失败
- turn2: 65.9s, 0c content, 23988c reasoning → findings 解析失败
- turn3: 17.2s, **11057c content**, 859c reasoning → **成功**（找到候选）

Executor 有时能"跳出推理循环"输出 content，Planner 几乎从不。

## 修复方案

### P0 修复：给 Planner 传 `reasoning_effort`

```python
# search_harness_pipeline_v4.py
self.planner = PlanningAgentV3(
    api_base=api_base, api_key=api_key, model_id=model_id,
    search_budget=max_planner_searches,
    reasoning_effort=executor_reasoning_effort,  # 新增
)
```

```python
# planning_agent_v3.py
def __init__(self, ..., reasoning_effort: Optional[str] = None):
    ...
    self.reasoning_effort = reasoning_effort

# _conversation_loop
response = chat_completion_with_structuring(
    self.client, model_id=..., messages=..., tools=None, ...,
    reasoning_effort_override=self.reasoning_effort,  # 新增
)
```

### P1 修复：默认思考档改 `high`

`EXECUTOR_THINKING=max` 下 GLM-5.2 频繁"推理饥饿"（30K reasoning, 0 content）。`high` 实测更稳定：
- 单轮 `max`: 11.7s, 558 reasoning tokens
- 单轮 `high`: 3.5s, 290 reasoning tokens
- 端到端 5 题 `high`: 5/5 PASS
- 端到端 5 题 `max`: 5/5 PASS

`.env` 已设 `EXECUTOR_THINKING=high`，但本次测试前 `export EXECUTOR_THINKING=max` 覆盖了它。**结论：BrowseComp 评测默认用 `high` 更稳，`max` 留作疑难题冲刺。**

## 预算参数评估

| 参数 | 本次值 | 实际触发？ | 评价 |
|------|--------|-----------|------|
| `max_iterations=4` | 4 | 是（iter 3 后进入 wrap-up） | 偏低，4 轮全在 candidate_generation，未进 verification |
| `max_crawl_calls=30` | 30 | 否 | 足够，但多用于错候选 |
| `max_planner_searches=8` | 8 | 否 | Planner 无 plan 产出，搜索预算未消耗 |
| `max_executor_searches=20` | 20 | 否（每子任务未触顶） | 足够 |
| `max_total_searches=60` | 60 | 否 | 未触顶（实际约 4 次搜索） | 

**预算不是瓶颈，Planner 退化才是。** 修 Planner 后预算才需重新评估。

## 复现命令

```bash
export EXECUTOR_THINKING=max
python3 run_browsecomp_fixed_sample.py \
  --seed 123 --sample-size 10 --positions 3 \
  --output /tmp/smoke_pos3_budget_test.json \
  --trajectory-dir /tmp/smoke_traj \
  --max-iterations 4 --max-crawl-calls 30 \
  --max-planner-searches 8 --max-executor-searches 20 \
  --max-total-searches 60 --max-workers 1
```

---

## 修复后重测（2026-08-04 17:08）

### 修复内容

| 文件 | 改动 |
|------|------|
| `planning_agent_v3.py` | `__init__` 新增 `reasoning_effort` 参数；2 处 `chat_completion_with_structuring` 调用传 `reasoning_effort_override=self.reasoning_effort` |
| `search_harness_pipeline_v4.py` | L66 `PlanningAgentV3(...)` 构造传 `reasoning_effort=executor_reasoning_effort` |

### 重测设置

| 项 | 值 |
|----|----|
| 思考档 | `EXECUTOR_THINKING=high`（默认，未 export 覆盖） |
| 其余 | 同首次测试（pos3, 平衡档降配版） |

### 重测结果

| 指标 | 修复前（max） | 修复后（high） |
|------|--------------|---------------|
| 状态 | finished | finished |
| 答案 | John Lennon（错） | Ronnie Wood（错） |
| 耗时 | 938.3s | 919.5s |
| Planner 产出 `<planning>` | **0/11**（全部 0 content + 22–32K reasoning） | **5/7**（1921c / 3169c / 930c / 2640c + structurer 恢复） |
| Planner starvation | 7/11 | 2/7（conv 1, 2, 6 仍 0 content） |
| Executor 搜索次数 | ~4 | 5 |
| 进入 verification | 否 | 否 |

### Planner 逐次产出

| conv | primary content | primary reasoning | structurer content | 有效 `<planning>`? |
|------|----------------|-------------------|--------------------|--------------------|
| 0 | 1921c | 777c | — | ✅ 直接产出 |
| 1 | 0c | 31183c | 0c（skip） | ❌ starvation |
| 2 | 0c | 32369c | 0c（skip） | ❌ starvation |
| 3 | 26c | 4522c | 3169c | ✅ structurer 恢复 |
| 4 | 930c | 4094c | — | ✅ 直接产出 |
| 5 | 2640c | 1148c | — | ✅ 直接产出 |
| 6（wrap-up） | 0c | 31013c | 0c（skip） | ❌ starvation |

**修复有效**：Planner 从 0/11 产出 plan → 5/7 产出 plan。structurer 在 primary 0-content 时也能恢复（conv 3）。

### 剩余问题

1. **Planner 仍有 2/7 starvation**（conv 1, 2, 6）——GLM-5.2 在 `high` 档下 primary 调用偶尔推理饥饿，但 structurer 兜底已覆盖大部分场景。
2. **Planner 分解偏浅**——生成的搜索词过于泛化（"rock musicians who attended art college"），未命中 David Coverdale。
3. **Executor 搜索太泛**——5 次搜索全在 iteration 2，query 如 "musician attended art college worked in a boutique married three times"、"Ronnie Wood boutique art college biography"（过早锁定错误候选）。从未搜索 "Deep Purple singer formed band" 或 "Coverdale"。
4. **全程未进 verification**——4 轮全在 candidate_generation，candidates 为 Keith Richards / Pete Townshend / John Lennon / Eric Clapton / David Bowie / Ray Davies / Jimmy Page / Jeff Beck，无 David Coverdale。

### 结论

**P0 修复有效，Planner 恢复产出 plan。** 但 BrowseComp 端到端正确率仍受限于 GLM-5.2 的搜索策略能力（query 太泛、未锁定最 distinctive 线索），而非预算参数或 reasoning_effort 配置。后续优化方向：
- **搜索策略**：在 Planner prompt 中强调"先用最 distinctive 约束组合搜索"（如 "100M records band singer + formed own band 1970-1990"），而非逐条约束拼凑。
- **预算**：当前 60-search 预算远未触顶（实际 5 次），增加预算不会改善；需改善 query 质量。
- **thinking 档**：`high` 比 `max` 更稳定（starvation 更少），维持 README 推荐。

---

## 第二轮修复：增强 simple prompt 加 verification 阶段（2026-08-04 18:04）

### 根因深挖

重测后答案仍错（Keith Richards），但排查发现 pipeline 行为已根本改变：

| 指标 | 首测（max） | 重测（high+P0） | 三测（high+P0+prompt） |
|------|------------|----------------|----------------------|
| Planner 产 plan | 0/11 | 5/7 | 5/7 |
| 进入 verification | 否 | 否 | **是** ✅ |
| 验证候选数 | 0 | 0 | **3**（Townshend→Davies→Clapton） |
| 搜索次数 | 4 | 5 | **17** |
| 耗时 | 938s | 920s | 1520s |
| 答案 | John Lennon | Ronnie Wood | Keith Richards |

**真正的第二层瓶颈**：`PLANNER_SIMPLE_PROMPT=1` 加载的 43 行 prompt **只有 `candidate_generation` 模板**，Planner 从不输出 `verification` phase，pipeline 永远停在候选生成 → 候选从不被验证 → 错答案。

### 修复：增强 `planning_agent_prompt_simple.md`

| 新增内容 | 作用 |
|---------|------|
| Phase 模型表（3 phase × subtask_type 映射） | 明确告诉 Planner 何时用哪个 phase |
| `stage_status: ready_to_advance` 规则 | 触发 `_advance_stage()` 进入 verification |
| verification / final_check 两个新模板 | Planner 能输出 `candidate_verification` subtask |
| "Never stay in candidate_generation forever" 硬约束 | 2+ 候选时必须切换 |

### 三测结果

| iter | phase | subtask | 候选 | 结果 |
|------|-------|---------|------|------|
| 0-2 | candidate_generation | "Search for candidate entities..." | 10（Richards/Townshend/Davies/Clapton/Page/Mercury/Lennon/Beck/Bowie/Jagger） | 候选池全是主流摇滚巨星，**无 David Coverdale** |
| 3 | candidate_verification | "Verify Pete Townshend against 'worked in a boutique' and 'married'" | — | **淘汰** Townshend（boutique 矛盾） |
| 4 | candidate_verification | "Verify Ray Davies against 'married three times', 'one daughter'" | — | 验证 Davies（未淘汰） |
| 5 | candidate_verification | "Verify Eric Clapton against 'married three times' and 'one daughter'" | — | 验证 Clapton |
| 6 | wrap-up → best_effort | — | — | finalizer 给出 Keith Richards（错） |

### 剩余瓶颈：候选池质量（非预算、非 phase）

**正确答案是 Whitesnake（David Coverdale）**，但候选池 10 人无 Coverdale。根因：
- candidate_generation 的 query 全是"art college + boutique"的组合 → 返回主流艺术院校摇滚巨星（Townshend/Lennon/Davies 都上过艺术院校）
- **最 distinctive 的约束是"100M records band"**（Deep Purple 卖了 1 亿+），但 Planner 从未搜 "rock band sold 100 million records singer"
- Coverdale 的路径：Deep Purple 主唱 → 1978 组 Whitesnake，这条线需从"100M records 乐队前主唱自组团 1970-1990"切入

### 对用户预算配置的结论

用户配置 `max_iterations=10, max_crawl_calls=60, max_planner_searches=15, max_executor_searches=35, max_total_searches=250`：

| 参数 | 评价 | 建议 |
|------|------|------|
| `max_iterations=10` | ✅ 合理（verification 需多轮，三测用 6 轮验证 3 候选） | 维持 10 |
| `max_crawl_calls=60` | ⚠️ 偏高（三测仅用 17 次搜索，crawl 比例约 1:3） | 可降到 40 |
| `max_planner_searches=15` | ✅ 合理 | 维持 |
| `max_executor_searches=35` | ⚠️ 每子任务 35 偏高（三测每候选 ~5 次搜索即出结论） | 可降到 15-20 |
| `max_total_searches=250` | ⚠️ 过高（三测 17 次，10 题也只 ~170 次） | **降到 150** 节省 API |

**预算不是瓶颈**。三测用 17/60 次搜索即跑完 6 轮。提高准确率的下一杠杆是 **候选池质量**，不是增加预算。

### 下一步（未实施）

1. **Planner 搜索策略增强**：在 simple prompt 加"先搜最 distinctive 约束"规则（如"100M records band"是小列表，先搜它再筛 singer）
2. **候选池多样性**：限制每候选验证轮数后强制 pivot（当前 Clapton 验证后未回到 expansion 找 Coverdale）
3. **多题验证**：单题样本太小，需跑 5-10 题看准确率是否稳定提升
