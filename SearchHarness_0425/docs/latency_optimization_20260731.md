# SearchHarness 耗时分析与优化方案 (2026-07-31)

## 耗时瓶颈数据 (v4 测试, 2483s 总耗时)

### 按模块耗时分布
| 模块 | 耗时 | 占比 | 调用次数 | 均/次 |
|------|------|------|---------|-------|
| query_critic._llm_based_check | 565.1s | 33.1% | 43 | 13.1s |
| _settle_subtask_with_critic | 539.4s | 31.6% | 14 | 38.5s |
| search_crawl_controller.evaluate | 386.3s | 22.6% | 9 | 42.9s |
| trajectory_recorder.finalize | 49.6s | 2.9% | 2 | 24.8s |
| tools.search_tools._crawl_url | 43.4s | 2.5% | 1 | 43.4s |
| planning_agent_v3._extract_planning | 37.1s | 2.2% | 3 | 12.4s |
| 其他 | 87.9s | 5.1% | - | - |
| **Top 3 占比** | **87.3%** | | | |

### 最长单次间隔 (串行 LLM 调用)
1. 247.0s — rewrite limit reached → next iteration (planner 重新规划)
2. 232.9s — planning parse fail → trajectory save (position 3 结束)
3. 164.5s — SubtaskCritic reject → planner re-plan
4. 129.6s — SubtaskCritic suggest_pivot → next SubtaskCritic
5. 117.1s — SubtaskCritic reject → next SubtaskCritic

### 关键发现
- **QueryCritic**: 43 次 LLM 调用,每次 13.1s — 每个搜索 query 都单独调 LLM 判重
- **SearchCrawlController**: 9 次 LLM 调用,每次 42.9s — 规则不明确时 fallback 到 LLM
- **_settle_subtask_with_critic**: 14 次,每次 38.5s — 含 planner.run 重试 + SubtaskCritic LLM
- 所有调用 **完全串行**,无并行/批量/缓存

## 2026 业界成熟做法参考

| 方法 | 预期收益 | 来源 |
|------|---------|------|
| Prompt/Prefix Caching | 50-70% prefill 时间 | [Agent Latency Budgets 2026] |
| 并行工具调用 | 40-70% (独立调用) | [Parallel Tool Calling 2026] |
| 批量/缓存 Critic | N次→1次 batch | 工程实践 |
| 规则优先/早退 | 跳过LLM | [SpecExit ICLR 2026] |
| 减少 hops | 乘法级减少 | [Agent Latency 2026] |
| Speculative 执行 | 18-66% | [SPORK arXiv:2607.03333] |

## 优化方案 (按 ROI 排序)

### P0: 批量 QueryCritic (预计省 400s+, 降低 16%+)
**问题**: 每个搜索 query 单独调 LLM 判重,43 次 × 13.1s = 565s
**方案**: 
- 一个 executor 轮的所有 queries 一次性 batch 判重 (1 次 LLM 代替 3-5 次)
- 或: 语义缓存 — 相似 query pattern 直接复用上次判定
- 规则层增强: 提高规则判定的覆盖率,减少 LLM fallback
**实现**: `query_critic.py` 增加 `batch_evaluate(queries: List[str])` 方法

### P1: SearchCrawlController 规则优先 (预计省 300s+, 降低 12%+)
**问题**: 9 次 LLM 调用 × 42.9s = 386s,很多是规则不明确时 fallback
**方案**:
- 扩展规则覆盖: 增加 more heuristics (如: 候选数 < 3 且有 pending_urls → crawl, 不需 LLM)
- 缓存决策: 相同 (phase, candidate_count, url_count) 组合复用上次决策
- 默认 use_llm=False,仅关键节点才调 LLM
**实现**: `search_crawl_controller.py` evaluate() 增加缓存层 + 扩展规则

### P2: Prompt/Prefix Caching (预计省 30-50% LLM prefill)
**问题**: 每次 LLM 调用全量 prefill (system prompt + tools + history)
**方案**:
- GLM-5.2 API 支持 prefix caching → 将 system prompt + tool defs 作为固定前缀
- 多轮对话复用前缀,只增量追加新内容
- 检查 OPENAI_BASE_URL (preview.llm.tenyunc.com) 是否支持 cache_control
**实现**: API 调用层增加 prefix caching 参数

### P3: 减少 reject→replan 循环 (预计省 200s+)
**问题**: SubtaskCritic reject → planner.run 重试 → 再 reject,最长 247s
**方案**:
- reject 时提供具体改进建议(已有 suggest_pivot,但 reject 没建议)
- planner 收到 reject 后用 fallback 多样化 subtask(已部分实现)
- 降低 max_rewrites 从 3 → 2,超限直接执行 fallback
- reject 后跳过 LLM critic,直接用规则判定
**实现**: `_settle_subtask_with_critic` 降 max_rewrites + reject 后跳过 LLM

### P4: 并行搜索 query (预计省 100s+)
**问题**: executor 串行执行搜索,每个 query 等 LLM 判重 + 搜索结果
**方案**:
- 一个 subtask 的多个 query 并行执行 (asyncio.gather)
- QueryCritic 批量判定后再并行搜索
- visit_urls 并行 crawl (ThreadPool,已有但限制 max_crawl_calls)
**实现**: `search_agent_v3.py` run() 改为 async + 并行

### P5: 早退/置信度阈值 (预计省 100s+)
**问题**: 即使已找到强候选,仍继续搜索到 budget 耗尽
**方案**:
- 候选置信度 > 0.9 且搜索 > 3 次 → 提前结束
- 已有 2+ 一致候选 → 跳过后续 candidate_generation
- SpecExit 思路: reasoning 充分性检测,提前终止
**实现**: pipeline.run() 增加早退条件

## 实施优先级
1. **P0 批量 QueryCritic** — 改动小,收益大 (33% → 可能降到 10%)
2. **P1 SearchCrawlController 规则优先** — 改动小,收益大 (22% → 可能降到 5%)
3. **P3 降 max_rewrites** — 一行改动,减少循环
4. **P2 Prefix Caching** — 需确认 API 支持
5. **P4/P5** — 改动较大,后续迭代

## 预期效果
- 当前: Position 1 = 758s, Position 3 = 2483s
- P0+P1+P3 后: 预计 Position 1 ~ 400s, Position 3 ~ 1200s (省 40-50%)
- 全部实施后: 预计 Position 1 ~ 250s, Position 3 ~ 800s (省 60-70%)
