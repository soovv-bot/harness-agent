# 冒烟测试分析 — 2026-08-04

## 测试配置
- 脚本: `run_browsecomp_fixed_sample.py`
- 样本: seed=123, k=10, position=3 (BrowseComp 题, 正确答案 = **Whitesnake**)
- 预算 (缩减): max_iterations=3, max_total_searches=30, planner=5, executor=10, crawls=15
- 模型: GLM-5.2 @ `https://preview.llm.tenyunc.com/v1`
- 输出: `results/smoke_position3_20260804.json` / `logs/trajectories_smoke_position3_20260804/`
- `EXECUTOR_THINKING=none`, `LLM_THINKING_BUDGET_TOKENS=0`

## 运行时间线
| 时刻 | 事件 |
|---|---|
| 13:41 | 首次跑 → 秒挂: **401 invalid_api_key** (旧 key `sk-7f8e…1d2c` 失效) |
| 13:45 | 用户更新 key 为 `sk-dbce…7172`，验证 200 OK |
| 13:46 | 重跑，planner 开始流式推理 (正常) |
| 13:48 | planner turn1: 92s, **31953 reasoning / 0 content** → 无 `<planning>` 块 → fallback |
| 13:48–13:52 | iter0 executor: turn1 62.9s 0-content 饥饿; turn2/3 仍 0-content → status=stopped_without_findings |
| 13:54–13:58 | iter1 executor: **正常** turn1 content=345 tool_calls=2, turn2 content=272 tool_calls=2 (search/visit_urls 成功) → status=completed |
| 14:02 | iter2 executor: 完成 (turn5 4437 reasoning, turn6 960 reasoning — thinking 基本禁用) → status=completed |
| 14:04:34 | finalizer: **0.6s, content=178, reasoning=62 — thinking 禁用生效**, status=**solved** |
| 14:04:34 | trajectory_finalized, pipeline_status=finished (3 iterations) |
| 14:04:44 | **grader 调用开始 → 失控**: 10s=8174 reasoning, 单调增长… |
| 14:14:48 | **614s / 434572 reasoning / 0 content** — 越过 600s 超时仍未停 |
| 14:15 | 手动 kill (grader 永久挂起, 结果文件未生成) |

## 最终状态
- pipeline: **finished** (finalizer solved, 候选 = Ronnie Wood / Mick Ronson / Mark Knopfler — 均非 Whitesnake, 答案错误)
- grader: **永久挂起** (被 kill, 无评分)
- 结果文件: **未生成** (grader 阻塞)

## 根因分析 (两个独立缺陷)

### 缺陷 1: tenyun 端点间歇性忽略 `reasoning_effort=none`
- `EXECUTOR_THINKING=none` + `LLM_THINKING_BUDGET_TOKENS=0` → 代码正确映射 effort="none" 并同时注入 top-level + extra_body
- 但端点行为**不一致**:
  - 生效时: executor 3.4s / 408 reasoning / content+tool_calls ✓ (iter2 turn1)
  - 忽略时: 60–92s / 30k+ reasoning / **0 content** 饥饿 ✗ (iter0/1 planner, iter0 executor)
- 同一参数同一次运行内 ~50% 调用被忽略 → 端点可靠性问题, 非代码 bug

### 缺陷 2: `_stream_completion` 无流级超时 (致命)
- `llm_reasoning_compat.py:319` `for chunk in stream:` 无任何时长上限
- `LLM_TIMEOUT_S=600` 只传给 OpenAI client 构造 (建连超时), **不打断活跃流**
- 后果: 当缺陷 1 触发 (none 被忽略 + 模型无限推理), 流永远不结束
- grader 调用 614s / 434k reasoning 仍在涨, 600s 超时完全失效 → 进程挂死
- 此缺陷使任何调用都有挂死风险, 必须先修

## 正常工作的部分 ✓
- API key 鉴权 (修复后)
- 数据集加载 (本地 `docs/seed123_k10_full.json`)
- pipeline 端到端流转 (planner → executor → critic → 3 iterations → finalizer)
- 工具执行: SERPER search 1.6–3.0s, visit_urls 1.1s
- finalizer 在 thinking 禁用时 0.6s 出答案
- 轨迹录制 (`task_000003.json` 含 55 events / 9 llm_calls / 3 iteration summaries)

## 建议 (真实测试前必须修复)
1. **修缺陷 2 (最高优先)**: 给 `_stream_completion` 加流级 wall-clock 超时 (如 `LLM_STREAM_TIMEOUT_S`), 超时则 `stream.close()` + 抛超时异常, 让上层 try/except 捕获降级。否则单次 grader/planner 调用即可挂死整个运行。
2. **缓解缺陷 1**: 加 `max_tokens` 硬上限 (限制 reasoning_content 总量), 或在 structurer fallback 已多次 0-content 时尽早放弃该 turn, 避免无谓重试。
3. 上述修复后重跑冒烟, 确认无挂死, 再跑真实预算 (10 iter / 250 searches)。

## 产出文件
- `logs/smoke_position3_20260804_run.log` (完整运行日志)
- `logs/smoke_position3_20260804_FAILED_401key.{json,log}` (旧 key 401 失败记录)
- `logs/trajectories_smoke_position3_20260804/GLM-5.2/task_000003.json` (轨迹, 9 LLM calls)
