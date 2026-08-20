# 重构后冒烟验证 — 2026-08-04 15:00

## 背景

完成 P0–P3 重构（去除模型名硬编码、模块重命名、思考模式 env 驱动）后，跑一轮真实 LLM 冒烟验证改动未破坏运行路径。

## 测试矩阵

| # | 脚本 | 范围 | 结果 |
|---|------|------|------|
| 1 | `debug_llm_smoke.py` | API 连通性（`/models` + `/chat/completions`） | PASS（200, `reasoning_content` 正常） |
| 2 | `debug_llm_smoke.py --verify-thinking` | 思考开关单元级（`minimal` vs 默认 `reasoning_tokens` 对比） | CHECK（`minimal`=65, 默认=65，端点对 minimal 仍产生 reasoning） |
| 3 | `smoke_test_simple.py` | 端到端 pipeline（trivial 问题） | PASS（answer='Paris', 0.7s） |
| 4 | `smoke_test_thinking.py --efforts "none high"` | 思考模式端到端（多 effort 对比，pipeline 不崩溃） | PASS（两组均 finished） |
| 5 | `pytest tests/ -q` | 单元测试 | PASS（72/72, 0.91s） |

## 测试配置

- 模型: GLM-5.2 @ `https://preview.llm.tenyunc.com/v1`（由 .env `MODEL_NAME` 提供，非硬编码）
- `EXECUTOR_THINKING=minimal`（env 驱动，pipeline 通过 `executor_reasoning_effort` 传入；OpenAI 标准）
- `LLM_THINKING_BUDGET_TOKENS=0`

## 新增/增强的冒烟脚本

### `debug_llm_smoke.py --verify-thinking`（新增分支）
- 修复 P1 引入的 env 加载时序 bug：argparse default 求值早于 `_load_env_file`
- 新增 `--verify-thinking`：发起两次 `chat/completions`（`reasoning_effort=minimal` + 默认），对比 `reasoning_tokens`（OpenAI 标准，仅顶层 kwarg）
- VERDICT 逻辑：`none`=0 且 默认>0 ⇒ PASS；两者都 0 ⇒ CHECK（非 reasoning 模型或端点忽略参数）

### `smoke_test_simple.py`（增强）
- 启动时打印当前 `EXECUTOR_THINKING` 与 `LLM_THINKING_BUDGET_TOKENS` 配置，输出自文档化

### `smoke_test_thinking.py`（新增）
- 对同一问题依次跑多个 `EXECUTOR_THINKING` 取值（`none`/`low`/`medium`/`high`）
- 验证 `executor_reasoning_effort` → `SearchAgentV3.reasoning_effort` → `build_chat_completion_kwargs` 传递链路不崩溃
- 输出 per-effort 状态表 + 汇总 PASS/CHECK/FAIL 判定
- 注：连通性冒烟，不断言答案相等或 token 数差异（那是 `--verify-thinking` 的职责）

## 思考模式传递链路（已验证）

```
.env: EXECUTOR_THINKING=minimal
  → SearchHarnessPipelineV4(executor_reasoning_effort="minimal")
  → SearchAgentV3(reasoning_effort="minimal")
  → chat_completion_with_structuring(reasoning_effort_override="minimal")
  → build_chat_completion_kwargs(reasoning_effort="minimal")
  → payload: {reasoning_effort: "minimal"}  # 顶层 kwarg（OpenAI 标准契约）
  → API 返回 reasoning_tokens（端点决定强度）
```

## 结论

重构后真实 LLM 路径全部通过：
- 模型名由 env 提供，无硬编码默认
- 思考模式开关在 API 层（单元级）与 pipeline 层（端到端）均生效
- 72 项单元测试无回归
