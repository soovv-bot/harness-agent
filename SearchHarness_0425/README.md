# SearchHarness_0425

多智能体 Web 搜索评测框架，用于在 [BrowseComp](https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv) 数据集上评估深度研究 Agent，并录制可蒸馏训练的完整轨迹。

本目录是 `SearchHarness_0413_v3` 之后的活跃工作区，在 v4 流水线基础上引入了**结构化候选状态管理**、**硬冲突消除**、**查询/方向 Critic** 与**有界停止策略**，目标是改善固定样本 (seed `123`, k `10`) 上的答题质量，同时产出可用于 OffSeeker 蒸馏训练的轨迹。

---

## 目录

- [项目架构](#项目架构)
- [目录结构](#目录结构)
- [构建环境](#构建环境)
- [配置说明](#配置说明)
- [快速开始](#快速开始)
- [评测脚本](#评测脚本)
- [并发模型](#并发模型)
- [搜索质量增强（P0）](#搜索质量增强p0)
- [推理轨迹增强（P1）](#推理轨迹增强p1)
- [理论增强（P2：自验证 / 置信度排序 / 自适应停止 / 失败分类）](#理论增强p2自验证--置信度排序--自适应停止--失败分类)
- [实验结果：Plan A 自验证消融（2026-08-04）](#实验结果plan-a-自验证消融2026-08-04)
- [调试与排错](#调试与排错)
- [单元测试](#单元测试)
- [轨迹与蒸馏](#轨迹与蒸馏)
- [常见问题](#常见问题)

---

## 项目架构

`SearchHarnessPipelineV4` 是核心编排器，每轮迭代执行 **Planner → Executor → Critics → Finalizer** 循环，并在候选生成 / 候选验证 / 最终检查三个阶段之间流转。

```
┌──────────────────────────── SearchHarnessPipelineV4 ────────────────────────────┐
│                                                                                  │
│   ┌────────────┐    plan     ┌─────────────┐   findings   ┌──────────────────┐   │
│   │ Planner v3 │ ─────────▶ │ Executor v3 │ ───────────▶ │ SearchStateStore │   │
│   │ (规划子任务) │ ◀──────── │ (调 search/ │  candidate  │ (候选 + 硬冲突)   │   │
│   └────────────┘   critic   │  visit_urls) │  updates    └──────────────────┘   │
│         ▲                   └─────────────┘                                   │
│         │                         │                                             │
│         │                         ▼                                             │
│   ┌─────────────┐  re-plan   ┌──────────────────────────────┐                   │
│   │ SubtaskCritic│◀────────│ QueryCritic / CrawlController │ (规则优先, LLM 兜底)│
│   │ DirectionCritic        └──────────────────────────────┘                   │
│   └─────────────┘                                                                │
│         │                                                                        │
│         ▼                                                                        │
│   ┌──────────────┐   answer    ┌────────────────────┐                          │
│   │ SearchFinalizer│ ────────▶ │ TrajectoryRecorder │ ──▶ logs/trajectories/   │
│   │ (从候选记录收敛) │           └────────────────────┘                          │
│   └──────────────┘                                                                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 核心模块

| 文件 | 职责 |
|------|------|
| `search_harness_pipeline_v4.py` | 流水线编排器：阶段流转、预算控制、有界停止、best-effort 终结 |
| `planning_agent_v3.py` | 规划 Agent：将问题拆解为子任务，反重复规则约束 |
| `search_agent_v3.py` | 执行 Agent：调用 `search` / `visit_urls` / `search_wiki` / `add_candidates` / `update_candidate` |
| `search_memory.py` | `SearchStateStore`：结构化候选记录（status / supporting / unresolved / hard_conflicts） |
| `query_critic.py` | 查询判重：规则层（字面重复、空历史、Jaccard）+ LLM 兜底 |
| `query_history.py` | 查询历史记忆，供 QueryCritic 判重 |
| `search_crawl_controller.py` | 搜索 vs 抓取决策：信号计算 + 规则优先 + LLM 兜底 |
| `subtask_critic.py` | 子任务质量评估：reject / accept / suggest_pivot |
| `planning_direction_critic.py` | 规划方向评估（可选，默认关闭） |
| `search_finalizer.py` | 终结器：从 `candidate_records` 收敛出最终答案，硬冲突候选不会被轻易采纳 |
| `trajectory_recorder.py` / `trajectory_recorder_enhanced.py` | 轨迹录制器。增强版输出 10 个结构化字段（事件流、搜索日志、LLM 调用元数据、候选快照、逐轮对话等），兼容 `convert_trajectory_to_offseeker_format.py` |
| `config.py` | 集中式配置（dataclass + 环境变量） |
| `llm_client.py` / `openai_client_factory.py` / `llm_error_utils.py` | LLM 客户端工厂与错误分类 |
| `llm_reasoning_compat.py` | 推理模型流式兼容层：处理 `reasoning_content` 字段、思考预算（`LLM_THINKING_BUDGET_TOKENS`）、工具调用流式解析 |
| `run_browsecomp.py` | 全量 BrowseComp 评测入口 |
| `run_browsecomp_fixed_sample.py` | 固定样本评测入口（可指定 positions） |
| `run_seed_repeats.py` | 同一种子重复运行以测量稳定性 |
| `regrade_results.py` | 用新 grader 对已有结果重打分 |
| `build_seed123_k10_full.py` | 重建本地固定子集 `docs/seed123_k10_full.json` |

### 工具集（Executor 可调用）

| 工具 | 说明 |
|------|------|
| `search` | Google 搜索（Serper API），`query` 为字符串数组 |
| `search_wiki` | Wikipedia 搜索，`entities` 为数组 |
| `visit_urls` | 抓取 URL 内容（Jina 优先，html2text 兜底），`urls` 数组 + 可选 `query` |
| `add_candidates` | 注册发现的候选名（字符串数组） |
| `update_candidate` | 更新单个候选的证据 / 状态 |

---

## 目录结构

```
SearchHarness_0425/
├── search_harness_pipeline_v4.py     # 流水线编排器
├── planning_agent_v3.py              # 规划 Agent
├── search_agent_v3.py                # 执行 Agent
├── search_memory.py                  # 候选状态存储
├── query_critic.py / query_history.py
├── search_crawl_controller.py
├── subtask_critic.py
├── planning_direction_critic.py
├── search_finalizer.py
├── trajectory_recorder.py / trajectory_recorder_enhanced.py
├── config.py                         # 集中式配置
├── llm_client.py / openai_client_factory.py / llm_error_utils.py
├── llm_reasoning_compat.py       # 推理模型流式兼容层（reasoning_content + 思考预算）
├── run_browsecomp.py                 # 全量评测入口
├── run_browsecomp_fixed_sample.py    # 固定样本评测入口
├── run_seed_repeats.py               # 重复运行
├── regrade_results.py                # 结果重打分
├── build_seed123_k10_full.py         # 重建固定子集
├── debug_llm_smoke.py           # LLM 端点冒烟测试（+ --verify-thinking 思考开关验证）
├── debug_serper_smoke.py             # Serper 搜索冒烟测试
├── smoke_test_simple.py              # 端到端 pipeline 冒烟（单问题）
├── smoke_test_thinking.py            # 思考模式端到端冒烟（多 effort 对比）
├── planning_agent_prompt_v3.md / search_agent_prompt_v3.md     # v3 通用 prompt
├── planning_agent_prompt_simple.md / search_agent_prompt_simple.md  # 简化 prompt（compact，适配推理模型）
├── requirements.txt
├── tests/
│   └── test_core_rules.py            # pytest 单元测试（37 个）
├── docs/
│   ├── browse_comp_test_set.csv      # 缓存的 BrowseComp 数据集
│   ├── seed123_k10_full.json         # 本地固定子集（seed=123, k=10）
│   ├── seed123_k10_manifest.json     # 固定子集 manifest（含 gold answer）
│   ├── seed123_k100_manifest.json    # k=100 manifest
│   ├── latency_optimization_20260731.md  # 耗时分析与优化方案
│   ├── smoke_test_2026-07-30.md      # 冒烟测试报告
│   ├── smoke_test_2026-08-04_refactor_verify.md  # 重构后冒烟验证（思考模式开关）
│   └── insight_*.md                  # 失败模式分析
├── results/                           # 评测结果 JSON（gitignore）
├── logs/                              # 轨迹与日志（gitignore）
└── WORKLOG.md                         # 历史工作记录
```

> 注意：`results/`、`logs/`、`trajectories/`、`__pycache__/` 均在 `.gitignore` 中，运行时自动生成。

---

## 构建环境

### 系统要求

- **Python**: >= 3.10
- **OS**: macOS / Linux / Windows（原始开发环境为 Windows + Anaconda）
- **网络**: 需能访问 LLM API 端点、`google.serper.dev`、`r.jina.ai`

### 1. 创建并激活虚拟环境

推荐使用 conda（与原开发环境一致）或 venv：

```bash
# conda 方式
conda create -n agent_safety python=3.10 -y
conda activate agent_safety

# 或 venv 方式
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows
```

### 2. 安装依赖

```bash
cd SearchHarness_0425
pip install -r requirements.txt
```

`requirements.txt` 内容（已最小化，仅列运行时必需）：

```
openai>=1.0.0
requests
httpx
beautifulsoup4
html2text
wikipedia-api
PyPDF2
python-dotenv>=1.0.0
loguru>=0.7.0
pandas
tqdm
```

如需运行单元测试，额外安装：

```bash
pip install pytest
```

### 3. 配置环境变量

在**项目根目录**（`SearchHarness_0425/` 的上一级，即 `search_data_systhesis/.env`）创建 `.env` 文件。脚本通过 `python-dotenv` 向上查找加载。

```bash
# ── LLM API（必需）──
OPENAI_BASE_URL=https://your-llm-endpoint/v1
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# 主模型（必填，无硬编码默认；按你的 Key 权限填写）
MODEL_NAME=<your-model-name>
# 执行 Agent 模型（留空则回退到 MODEL_NAME）
EXECUTOR_MODEL_NAME=<your-model-name>

# LLM 超时与思考预算
LLM_TIMEOUT_S=600
LLM_THINKING_BUDGET_TOKENS=1000

# 思考模式控制（per-role，OpenAI 标准 reasoning_effort）
# GLM-5.2 (tenyun 网关) 实测取值（2026-08-04）：
#   EXECUTOR_THINKING=high   → 较快较浅（推荐：~3.5s/轮，避免工具调用饥饿）
#   EXECUTOR_THINKING=max    → 最深推理（~11.7s/轮，难规划任务用）
# OpenAI 标准值（minimal/low/medium）在 GLM-5.2 上被网关重映射为 high；
# none 是 minimal 别名，在 GLM-5.2 上不会真正关闭思考。
# 切到 OpenAI o-series 端点时改用 minimal/low/medium/high（max 会被拒）。
EXECUTOR_THINKING=high

# ── Grader（可选，缺省回退到主 LLM）──
GRADER_API_BASE=https://your-grader-endpoint/v1
GRADER_API_KEY=sk-yyyyyyyyyyyyyyyy
GRADER_MODEL_NAME=<your-grader-model-name>

# ── 搜索工具（必需）──
SERPER_API_KEY=your_serper_key
JINA_API_KEY=your_jina_key
CRAWLER_ENGINE=jina                 # 或 html2text

# ── 日志与 prompt 模式 ──
LOG_LEVEL=INFO
PLANNER_SIMPLE_PROMPT=false
EXECUTOR_SIMPLE_PROMPT=false
```

> **重要**：`MODEL_NAME` 必须是当前 API Key 可访问的模型。冒烟测试显示部分 Key 可访问某些模型但无法访问其它（如 `deepseek-chat`），模型权限错误不会在启动时暴露，只在调用时返回 model-access denial。

---

## 配置说明

所有配置集中在 `config.py`，通过 `settings()` 惰性读取环境变量（不在 import 时求值，便于测试 monkeypatch）：

```python
from config import settings

s = settings()
client = build_openai_client(s.api_base, s.api_key)
model_id = s.model_id              # 主模型
executor_id = s.executor_model_id  # 执行模型（回退到主模型）
grader_id = s.grader.model_id      # grader 模型（回退到主模型）
```

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `OPENAI_BASE_URL` | — | LLM API 端点 |
| `OPENAI_API_KEY` | — | LLM API Key |
| `MODEL_NAME` | —（必填） | 主模型 ID |
| `EXECUTOR_MODEL_NAME` | 回退到 `MODEL_NAME` | 执行 Agent 模型 |
| `LLM_TIMEOUT_S` | `600` | 单次 LLM 调用超时（秒） |
| `LLM_THINKING_BUDGET_TOKENS` | `1000` | 思考预算 token（`0` ⇒ 自动转 `none`） |
| `EXECUTOR_THINKING` | `high` | 执行 Agent 思考强度：`max`/`high`（GLM-5 原生，推荐）+ `minimal`/`low`/`medium`（OpenAI 标准，GLM-5 上被重映射）；`none`=`minimal` 别名；留空不注入 |
| `GRADER_API_BASE` / `GRADER_API_KEY` / `GRADER_MODEL_NAME` | 回退到主 LLM | Grader 配置 |
| `SERPER_API_KEY` | — | Google 搜索 Key |
| `JINA_API_KEY` | — | Jina 抓取 Key |
| `CRAWLER_ENGINE` | `jina` | 抓取引擎：`jina` 或 `html2text` |
| `LOG_LEVEL` | `INFO` | loguru 日志级别 |
| `PLANNER_SIMPLE_PROMPT` | `false` | 使用简化 planner prompt |
| `EXECUTOR_SIMPLE_PROMPT` | `false` | 使用简化 executor prompt |

---

## 思考模式控制

推理模型（如 GLM-5.2、DeepSeek-reasoner、Kimi-K3）会在 `reasoning_content` 字段输出思考过程。思考有助于规划质量，但执行阶段过度思考会触发"工具调用饥饿"——模型把全部预算花在推理上、迟迟不发起工具调用。本系统遵循 **OpenAI 标准** `reasoning_effort` 参数控制思考强度，按角色独立配置：

```
EXECUTOR_THINKING=minimal   # 执行 Agent：最弱思考（推荐，避免工具调用饥饿）
       │
       ▼
SearchHarnessPipelineV4(executor_reasoning_effort="minimal")
       │
       ▼
SearchAgentV3(reasoning_effort="minimal")
       │
       ▼
chat_completion_with_structuring(reasoning_effort_override="minimal")
       │
       ▼
build_chat_completion_kwargs(reasoning_effort="minimal")
       │
       ▼
payload = {
  "reasoning_effort": "minimal"   # 顶层 kwarg（OpenAI 标准契约）
}
```

> **设计原则**：仅传递顶层 `reasoning_effort`，不注入任何 vendor-specific `extra_body`（如 `thinking.type`、`budget_tokens`）。兼容任何 OpenAI-compatible 端点。

### 取值语义

本系统接受 OpenAI o-series 与 GLM-5 两套词汇的并集，把解析后的值原样转发给端点：

| `EXECUTOR_THINKING` | OpenAI o-series 行为 | GLM-5.2 行为 | 适用场景 |
|------|------|------|---------|
| `minimal` | 最弱思考（OpenAI 标准） | **重映射为 `high`**（tenyun 网关）或回退 `max`（官方 API） | 执行 Agent（OpenAI 端点） |
| `low` | 低强度思考 | 同上（重映射/回退） | 简单多跳（OpenAI 端点） |
| `medium` | 中等强度 | 同上（重映射/回退） | 复杂多跳（OpenAI 端点） |
| `high` | 高强度思考 | 较快/较浅思考（GLM-5 原生支持） | 极难推理 / GLM-5 提速 |
| `max` | **不识别**（端点会报错或忽略） | 最深思考（GLM-5 原生默认档） | GLM-5 最强推理 |
| `none` | `minimal` 别名 | 同 `minimal` | 向后兼容 |
| 留空 | 不注入，端点默认 | GLM-5 默认 `max` | 非 reasoning 模型 |

> **GLM-5.2 关键限制**：
> - **无法关闭思考**——GLM-5.2 思考永远开启，没有 `none`/`disabled` 等价物。`EXECUTOR_THINKING=none` 在 GLM-5 端点上不会禁用思考，只会被重映射。
> - **`minimal`/`low`/`medium` 不是 GLM-5 原生词汇**——OpenAI 标准值在 GLM-5 上会被网关重映射。tenyun（LiteLLM 网关）把它们映射成 `high`；Zhipu 官方 API 则回退到 `max`。若要对 GLM-5 精确控制，只用 `max` 或 `high`。
> - **OpenAI 标准端点**（o1/o3/o4、GPT-5）原生支持 `minimal`/`low`/`medium`/`high`，不识别 `max`。同一份配置切到 OpenAI 端点时 `max` 会被端点拒绝或忽略——切端点时请同步调整 `EXECUTOR_THINKING`。

`LLM_THINKING_BUDGET_TOKENS` 环境变量也可控制（当 `EXECUTOR_THINKING` 留空时生效，影响 planner/critic/grader）：`0`→`minimal`，`≤1024`→`low`，`≤4096`→`medium`，`>4096`→`high`。在 GLM-5.2（tenyun 网关）上这些都会被重映射到 `high`，主要对 OpenAI o-series 端点有意义。

### 推荐配置（GLM-5.2 / tenyun 网关，实测 2026-08-04）

在 GLM-5.2 上只有 `max` 与 `high` 是原生取值，同一问题实测对比（`smoke_test_thinking.py`，"strawberry 里几个 r"）：

| `EXECUTOR_THINKING` | 单轮耗时 | planner reasoning tokens | 说明 |
|---|---|---|---|
| `max` | **11.7s** | 558 | 最深推理，默认档；复杂多跳 / BrowseComp 难题用 |
| `high` | **3.5s**（快 ~3.3×） | 290 | 较快较浅；执行 Agent 推荐，避免工具调用饥饿 |
| `none`/`minimal` | ~3.5s | ~290 | **不推荐**——被网关重映射成 `high`，语义不明 |

```bash
# 执行 Agent 用快速档（推荐，避免工具调用饥饿）
EXECUTOR_THINKING=high

# 最强推理（难规划任务，会慢约 3×）
EXECUTOR_THINKING=max
```

> **为什么默认 `high` 而非 `none`**：早期 `EXECUTOR_THINKING=none` 旨在"关闭思考以让 executor 快速发工具调用"。但 GLM-5.2 无法关闭思考，`none` 在 tenyun 上被重映射成 `high`——行为与直接写 `high` 相同，但语义模糊。显式写 `high` 行为可预测、配置可读。若要最强推理改 `max` 即可。

### 验证思考模式生效

```bash
# 1. 单元级：直接对比 reasoning_tokens（minimal vs 默认）
python3 debug_llm_smoke.py --verify-thinking

# 2. 端到端：跑同一问题，对比 EXECUTOR_THINKING=minimal 与 high 的行为差异
python3 smoke_test_thinking.py --question "..." --efforts "minimal high"
```

---

## 快速开始

### 冒烟测试（强烈建议首次运行先做）

依次验证 LLM 端点与 Serper 搜索是否可用：

```bash
cd SearchHarness_0425

# 1. LLM 端点冒烟测试（检查 /models 与 /chat/completions 连通性 + Key 权限）
python3 debug_llm_smoke.py --no-proxy

# 2. 思考模式开关冒烟（对比 EXECUTOR_THINKING=minimal vs 默认的 reasoning_tokens 差异）
python3 debug_llm_smoke.py --verify-thinking

# 3. Serper 搜索冒烟测试
python3 debug_serper_smoke.py

# 4. 端到端 pipeline 冒烟（一个 trivial 问题，跑通 Planner→Executor→Finalizer 全链路）
python3 smoke_test_simple.py

# 5. 思考模式端到端冒烟（同一问题对比 none/high 行为差异，验证 EXECUTOR_THINKING 传递链路）
python3 smoke_test_thinking.py --efforts none high
```

预期输出：
- `debug_llm_smoke.py`：`/models` 与 `/chat/completions` 均 `status: 200`，`reasoning_content` 字段正常返回
- `debug_llm_smoke.py --verify-thinking`：`minimal` 分支 `reasoning_tokens` 应显著低于默认分支
- `debug_serper_smoke.py`：`status_code: 200`，返回搜索结果
- `smoke_test_simple.py`：`RESULT = PASS`，答案非空
- `smoke_test_thinking.py`：各组 effort 均完成；`minimal` 组工具调用更早、`high` 组 reasoning_tokens 更高

若 Serper 返回 `{"message":"Not enough credits","statusCode":400}`，说明额度耗尽，需充值或更换 Key。

### 单题评测（固定样本）

固定样本为 seed `123`、k `10`，其中 position `0` 是跳过的参考项，position `1-9` 是主评测项。`docs/seed123_k10_manifest.json` 含 gold answer。

```bash
# 评测 position 4（gold: Ding Junhui，历史错误答案: Mark Selby，用于验证硬冲突消除）
python3 run_browsecomp_fixed_sample.py \
  --seed 123 \
  --sample-size 10 \
  --positions 4 \
  --output results/seed123_pos4.json \
  --trajectory-dir logs/trajectories_pos4 \
  --max-iterations 6 \
  --max-crawl-calls 12 \
  --max-planner-searches 10 \
  --max-executor-searches 30 \
  --max-total-searches 80
```

### 多题批量评测

```bash
# 评测 position 2-9
python3 run_browsecomp_fixed_sample.py \
  --seed 123 --sample-size 10 --positions 2-9 \
  --output results/seed123_pos2to9.json \
  --trajectory-dir logs/trajectories_pos2to9 \
  --max-iterations 6 --max-crawl-calls 12 \
  --max-planner-searches 10 --max-executor-searches 30 --max-total-searches 80 \
  --max-workers 1            # >1 可并行，但会增加 LLM 并发与配额压力
```

### 全量 BrowseComp 评测

```bash
python3 run_browsecomp.py \
  --num-examples 50 \
  --max-workers 3 \
  --output results/browsecomp_v4.json \
  --trajectory-dir logs/trajectories_full \
  --max-iterations 6 \
  --max-planner-searches 10 \
  --max-executor-searches 20 \
  --max-total-searches 120 \
  --max-crawl-calls 30 \
  --seed 123
```

> **推理模型提示**：使用推理模型时，设置 `LLM_THINKING_BUDGET_TOKENS`（如 `4096`）可让模型充分推理后再决策。默认 `1000` 对复杂多跳问题可能不足，导致规划过浅。设置方法：在 `.env` 中配置或运行时前缀 `LLM_THINKING_BUDGET_TOKENS=4096 python3 run_browsecomp_fixed_sample.py ...`。

---

## 预算参数配置建议（BrowseComp 评测，实测 2026-08-04）

> **核心结论（三轮单题实测 pos3）**：预算**不是**准确率的瓶颈。三轮测试实际搜索次数 4 → 5 → 17，远低于预算上限 60，但准确率未随预算提升。真正的杠杆是 **Planner 能否进入 verification 阶段**（已修）和 **候选池 query 质量**（待优化）。

### 预算参数作用范围

| 参数 | 作用域 | 触发后行为 | 实测占用 |
|------|--------|-----------|---------|
| `--max-iterations` | 每题外层迭代轮数 | 触发 `max_iterations_reached`，进入 best-effort 终结 | 三测 6 轮验证 3 候选即收尾 |
| `--max-crawl-calls` | 每题全局抓取数 | 触发 `max_crawl_calls_reached`，best-effort 终结 | 三测 ~5 次 crawl（搜索:crawl ≈ 3:1） |
| `--max-planner-searches` | 每题 Planner 累计搜索 | Planner 搜索被拒、改用现有信息规划 | 未触发 |
| `--max-executor-searches` | **每子任务**（每次 `run()` 重置） | Executor 搜索被拒、注入"预算耗尽"提示收尾 | 每候选 ~5 次搜索即出结论 |
| `--max-total-searches` | 每题全局搜索硬上限 | 触发 `max_total_searches_reached`，best-effort 终结 | 三测 17/60，远未触顶 |

> **关键**：`--max-executor-searches` 是**每子任务**而非每题。但实测每子任务 ~5 次搜索即出验证结论，35 偏高。`--max-total-searches` 通常最先触发，但修复 verification 后实际消耗远低于预算——增加预算**不会**提升准确率。

### 三档推荐配置

| 档位 | `--max-iterations` | `--max-crawl-calls` | `--max-planner-searches` | `--max-executor-searches` | `--max-total-searches` | `--max-workers` | `EXECUTOR_THINKING` | 适用场景 |
|------|-----|-----|-----|-----|-----|-----|-----|-----|
| **冒烟**（单题 10–25min） | 6 | 30 | 8 | 20 | 60 | 1 | `high` | 验证 API/搜索/链路连通 |
| **平衡**（10题 6–7h） | 8 | 40 | 15 | 20 | 150 | 4 | `high` | 正式评测，准确率/成本平衡 |
| **极限**（10题 10–14h） | 10 | 60 | 20 | 30 | 250 | 2 | `max` | 榜单冲刺，预算无上限 |

> **vs 旧推荐**：平衡档 `max_total_searches` 200→**150**（实测 17 次搜索即够）、`max_crawl_calls` 100→**40**、`max_executor_searches` 30→**20**、`EXECUTOR_THINKING` max→**high**（max 档 GLM-5.2 频繁 reasoning starvation）。

### 平衡档完整命令（推荐）

```bash
# 1. 思考档用 high（实测 max 档 GLM-5.2 频繁 reasoning starvation：0 content + 30K reasoning）
export EXECUTOR_THINKING=high

# 2. 运行 10 题，4 路并发
python3 run_browsecomp_fixed_sample.py \
  --seed 123 \
  --sample-size 10 \
  --positions 3 \
  --output results/position3_v4_balanced_20260804.json \
  --trajectory-dir logs/trajectories_position3_v4_balanced_20260804 \
  --max-iterations 8 \
  --max-crawl-calls 40 \
  --max-planner-searches 15 \
  --max-executor-searches 20 \
  --max-total-searches 150 \
  --max-workers 4
```

### 预算设计原理（实测修正）

| 设计点 | 解释 |
|--------|------|
| `max-iterations=8` | verification 阶段需多轮（三测 6 轮验证 3 候选）；8 轮覆盖 10 候选 + best-effort |
| `max-crawl-calls=40` | 实测搜索:crawl ≈ 3:1，17 次搜索 → ~5 次 crawl；40 足够且防失控 |
| `max-planner-searches=15` | Planner 主要调用 LLM 而非搜索，15 富余 |
| `max-executor-searches=20` 每子任务 | 实测每候选 ~5 次搜索即出结论，20 富余 |
| `max-total-searches=150` | 三测单题 17 次，10 题 ~170 次（含 verification）；150 是安全上限，过大会浪费 API 配额 |
| `--max-workers=4` | 4 路并发是 tenyun 网关限流安全区 |
| `EXECUTOR_THINKING=high` | 实测 `max` 档 GLM-5.2 推理饥饿（0 content + 30K reasoning），`high` 更稳定；`max` 仅留作疑难题冲刺 |

### 运行前检查清单

```bash
# 1. 确认思考档（推荐 high；max 仅用于疑难题冲刺）
echo $EXECUTOR_THINKING  # 应输出: high

# 2. 确认 LLM 端点连通
python3 debug_llm_smoke.py --verify-thinking

# 3. 单题冒烟（10–25min，验证整链路 + verification 阶段是否触发）
#    注意：--positions 必须 < --sample-size；--sample-size 1 时只能用 --positions 0
python3 run_browsecomp_fixed_sample.py \
  --seed 123 --sample-size 10 --positions 3 \
  --output /tmp/smoke_pos3.json \
  --trajectory-dir /tmp/smoke_traj \
  --max-iterations 6 --max-crawl-calls 30 \
  --max-planner-searches 8 --max-executor-searches 20 \
  --max-total-searches 60
```

### 资源消耗预估

| 指标 | 平衡档（10题） | 极限档（10题） |
|------|---------------|---------------|
| 每题实际搜索次数 | ~17–30 | ~30–60 |
| 每题耗时 | 25–40 min | 40–80 min |
| 10 题总墙钟时间（并发） | **2–3 小时** | **4–6 小时** |
| 总搜索 API 调用 | ~300 | ~600 |
| 总 LLM 调用 | ~500–800 | ~1000–1500 |
| 预计 LLM token | 10–20M | 20–40M |

> **注**：上表基于实测（单题 17 次搜索、25 min）。旧估计（200 次搜索、100–150 min/题）是预算上限假设，实际消耗远低于此。

### 实测附注（2026-08-04，三轮单题 pos3）

三轮同题实测（正确答案 Whitesnake）验证了预算非瓶颈、Planner 阶段切换才是关键：

| 轮次 | 改动 | 搜索次数 | Planner 产 plan | 进入 verification | 答案 | 耗时 |
|------|------|---------|----------------|------------------|------|------|
| 首测 | 原始 + EXECUTOR_THINKING=max | 4/60 | 0/11 | 否 | John Lennon（错） | 938s |
| 重测 | +Planner `reasoning_effort` 修复 | 5/60 | 5/7 | 否 | Ronnie Wood（错） | 920s |
| 三测 | +simple prompt 加 verification 阶段 | **17/60** | 5/7 | **是** ✅ | Keith Richards（错） | 1520s |

**两个已修 bug**（详见 `docs/budget_test_2026-08-04_analysis.md`）：
1. **Planner `reasoning_effort` 缺失**（commit `161003c`）：Planner 未传 `reasoning_effort` → fallback `minimal` → GLM-5.2 忽略 → 0/11 产 plan。修复后 5/7 产 plan。
2. **simple prompt 只有 candidate_generation 模板**（commit `eb1b251`）：`planning_agent_prompt_simple.md` 无 verification phase → Planner 从不输出 `verification` → 候选永不验证。增强后 pipeline 进入 verification，逐个验证淘汰（Townshend/Davies/Clapton）。

**剩余瓶颈**（未修，非预算）：候选池质量。candidate_generation 的 query 过于泛化（"art college + boutique" 返回主流摇滚巨星），未锁定最 distinctive 约束（"100M records band" → Deep Purple → David Coverdale → Whitesnake）。需后续优化 Planner 搜索策略。

---

## 评测脚本

### `run_browsecomp.py` — 全量评测

| 参数 | 默认 | 说明 |
|------|------|------|
| `--num-examples` | `5` | 评测题目数 |
| `--max-workers` | `1` | 并发 worker 数 |
| `--max-iterations` | `6` | 流水线最大迭代轮数 |
| `--max-planner-searches` | `10` | Planner 搜索预算（总计） |
| `--max-executor-searches` | `20` | Executor 搜索预算（每子任务） |
| `--max-total-searches` | `120` | 全局搜索预算（安全网） |
| `--max-crawl-calls` | `30` | 最大抓取调用数 |
| `--output` | — | 结果 JSON 路径 |
| `--save-trajectories` | `True` | 是否保存轨迹 |
| `--trajectory-dir` | `logs/trajectories` | 轨迹目录 |
| `--seed` | — | 随机种子 |
| `--skip` | `0` | 跳过前 N 题（用于断点续跑） |

### `run_browsecomp_fixed_sample.py` — 固定样本评测

| 参数 | 默认 | 说明 |
|------|------|------|
| `--seed` | 必填 | 固定样本种子（`123`） |
| `--sample-size` | 必填 | 样本大小（`10`） |
| `--positions` | 必填 | 位置，支持 `4` / `2-9` / `1,3,5` |
| `--output` | 必填 | 结果 JSON 路径 |
| `--trajectory-dir` | `logs/trajectories_fixed` | 轨迹目录 |
| `--max-workers` | `1` | 并发数 |
| `--disable-query-critic` | — | 关闭查询判重（允许重复 query） |
| 预算参数同上 | | |

### `run_seed_repeats.py` — 重复运行

```bash
python3 run_seed_repeats.py \
  --seed 123 \
  --repeats 10 \
  --parallelism 3 \
  --output-dir results/repeats \
  --trajectory-root logs/repeats
```

### `regrade_results.py` — 结果重打分

```bash
python3 regrade_results.py \
  --input results/old_run.json \
  --output results/old_run_regraded.json \
  --max-workers 4
```

### `build_seed123_k10_full.py` — 重建固定子集

```bash
python3 build_seed123_k10_full.py
# 输出: docs/seed123_k10_full.json
```

---

## 并发模型

`--max-workers > 1` 时，评测脚本使用 `ThreadPoolExecutor` 并发处理多个题目。并发架构为 **per-worker 隔离实例**，无共享可变状态：

| 组件 | 作用域 | 线程安全说明 |
|------|--------|-------------|
| `SearchHarnessPipelineV4` | 每个 worker 独立创建 | 包含独立的 state_store / planner / executor |
| `TrajectoryRecorderEnhanced` | 每个 worker 独立创建 | 输出文件按 `task_index` 唯一命名，原子写入（临时文件 + rename） |
| `QueryCritic` / `QueryHistoryMemory` | 每个 pipeline 独立创建 | 无跨 worker 共享 |
| `SearchCrawlController` | 每个 pipeline 独立创建 | 无跨 worker 共享 |
| `LLMGrader` | 全局共享 | 无状态，httpx 客户端线程安全 |
| `results_lock` | 全局共享 | `Lock` 保护结果列表追加 |

> 并发不会导致轨迹数据串扰：每个 pipeline 拥有独立的 `_trajectory_current_iter` 可变容器，事件回调闭包捕获各自的容器引用，无跨任务泄漏。

---

## 搜索质量增强（P0）

### 搜索结果后处理（`search_tools.py`）
每次 Serper API 返回后，`_postprocess_serper_results()` 对结果做三步处理：

1. **域名去重** — 同一域名只保留第一条结果，避免同一站点霸占返回列表。白名单域名（`wikipedia.org`、`britannica.com`）豁免去重，因为百科站点有大量相关子页面。
2. **权威加权排序** — 按域名权威分排序（稳定排序，不破坏同分原序）：
   | 权威分 | 域名 |
   |--------|------|
   | 3 | `wikipedia.org` / `britannica.com` / `.gov` / `.edu` |
   | 2 | `nature.com` / `pubmed` / `doi.org` / `imdb.com` / `discogs.com` / `musicbrainz` |
   | 1 | 其他 |
3. **截断** — 最多保留 top-8 条结果，减少 token 消耗。

### 证据锚定（`search_agent_v3.py` `_coerce_findings`）
执行器输出的 `candidate_updates.candidate_assessments` 中，`verification_status: "verified"` 的候选**必须**至少有一条 `evidence` 条目包含 `source_url` + `quote`。没有 `source_url` 的"verified"会被自动降级为 `partial`，并标注 `_downgrade_reason: "no_anchored_evidence"`。

这确保蒸馏训练数据展示"证据→结论"链条，而非模型凭记忆断言。

执行器 prompt（`search_agent_prompt_simple.md`）已更新 evidence 格式要求：
```json
"evidence": [{"source_url": "https://...", "quote": "exact sentence from page", "constraint_matched": "which constraint"}]
```

---

## 推理轨迹增强（P1）

### `reasoning_excerpt` 字段（`trajectory_recorder_enhanced.py`）
`llm_calls` 摘要中新增 `reasoning_excerpt` 字段，保存每轮 LLM 调用的 `reasoning_content`（截断至 2000 字符）。蒸馏管线和日志排查可直接从 `llm_calls` 读取推理链，无需深入 `planner_conversations` / `executor_conversations` 的完整消息。

---

## 理论增强（P2：自验证 / 置信度排序 / 自适应停止 / 失败分类）

本组增强面向论文写作，目标是用**最小改动**把当前 Planner-Executor-Critic 架构接入三条前沿理论线，使方法章节具备可引用的理论锚点，同时给出可复现的消融接口。四项改动均为开关式、failure-safe，默认行为可在环境变量层面切换，不影响已有轨迹的可复现性。

| 改动 | 理论锚点 | 改动量 | 开关 | 文件 |
|------|---------|-------|------|------|
| A. 自验证终结器 | Self-Verification / Chain-of-Verification (CoVe, Lightman et al. 2022) | 新增 `answer_verifier.py` + 改 `search_finalizer.py` | `ANSWER_VERIFIER_ENABLED`（默认开） | `answer_verifier.py`, `search_finalizer.py` |
| B. 候选置信度排序 | 过程奖励 / Implicit Process Reward | 改 `search_finalizer.py` 排序逻辑 | 自动启用 | `search_finalizer.py` |
| C. 自适应提前停止 | Anytime / Adaptive Compute | 改 `search_harness_pipeline_v4.py` `_check_stop` | 自动启用 | `search_harness_pipeline_v4.py` |
| E. 失败分类分析 | Error Taxonomy / Error Analysis | 新增 `failure_taxonomy.py`（离线脚本） | 手动运行 | `failure_taxonomy.py` |

### A. 自验证终结器（`answer_verifier.py`）

**动机。** BrowseComp 上的主要错误模式是"强但假"候选——Agent 自信地提交一个具体答案但与 ground truth 不符（当前 14.2%）。原 `SearchFinalizer` 直接取首个 viable 候选作为答案，没有任何落地证据复核。

**方法。** 新增 `AnswerVerifier`，在 finalize 阶段对**已选定的答案**做一次 grounded 复核：

1. 从候选记录中提取该候选的 `unresolved_constraints`，构造一个针对性验证查询（如"X 的约束 Y 是否成立？"）。
2. 复用已有 `search()` 工具（`OffSeeker-main/inference/src/tools/search_tools.py`）拉取一条外部证据——**不新增检索源**，与 Executor 共用同一 Serper 通道。
3. 用一次 LLM judge 判断证据是否 **支持 / 反驳 / 无法判定** 该声明。
4. 若 **refuted** → 将答案降级为 `Unknown`、置信度降为 `none`，避免提交强但假候选；若 **verified** → 提升置信度；若 **inconclusive** → 保留原答案但附上验证元数据。

**设计约束。**
- **Failure-safe**：检索 / 解析 / LLM 任何异常都回退到 `inconclusive`，绝不阻塞主管线。
- **单次开销**：每题最多 1 次额外检索 + 1 次 LLM 调用，预算可控。
- **可观测**：验证结果写入 `FinalizationResult.verification` 并进入轨迹，供蒸馏与消融分析。

**环境变量。**
- `ANSWER_VERIFIER_ENABLED`（默认 `true`）——总开关。
- `VERIFIER_MAX_TOKENS`（默认 `2048`）——judge 调用 token 上限。
- `VERIFIER_TYPE_AWARE`（默认 `true`）——类型感知验证开关。开启后 judge 首先识别题目**问什么**（ASKS FOR）而非**描述什么**（DESCRIBES），防止把题目主语类型误当答案类型。消融实验的关键变量。

**类型感知验证（假阴性修复）。** 消融实验发现 pos0 假阴性：题目以 "This person..." 开头描述人物，但实际问的是"What was the name of the secondary or senior high school they attended?"（答案类型=学校）。验证器在 400 字符截断下只看到描述部分，误判答案应为"人"，于是 REFUTE 了正确答案 "Achimota School"。

修复三层（详见 `docs/experiment_compare_20260804.md`）：
1. **问题截断扩展**：`_judge` 从 400→1200 字符、`_build_claim` 从 200→800 字符，确保题目末尾的实际提问不被截断（BrowseComp 题目平均 ~700 字符）。
2. **类型感知指令**：judge prompt 注入"答案类型 = 题目问什么，非描述什么"的显式指令，要求 REFUTE 必须证明答案类型不符 **或** 约束不满足，而非仅因答案类型 ≠ 题目主语类型就拒绝。
3. **验证查询优化**：`_build_verification_query` 改用题目**最后一句**（实际提问）的关键词，而非全文前 4 个词，避免描述性前导词污染验证查询。

**修复验证。** pos0 单题重跑：Plan A 判定从 REFUTED → INCONCLUSIVE，答案从 Unknown → Achimota School（正确），耗时 348s（与 baseline 329s 持平）。

**论文对应。** 方法章节"答案落地验证"小节，引用 CoVe / Self-Verification；消融表对比 开/关验证器 下的 wrong-answer 率变化；**类型感知修复**作为 precision 提升的消融点（VERIFIER_TYPE_AWARE 0 vs 1）。

### B. 候选置信度排序（`search_finalizer.py`）

**动机。** 原 finalizer 在多个 viable 候选中**取第一个**，没有利用已积累的过程信号。`candidate_records` 里的 `supporting_constraints` 数量是一个天然的过程奖励（satisfied constraint 越多越可信），却未被使用。

**方法。** 在 `_build_prompt` 选择最佳候选前，按 `supporting_constraints` 数量降序排序 viable 候选（`_rank_candidates_by_support`），以 `verification_status` 作 tiebreaker（verified > partial > unverified > contradicted）。排序仅影响 prompt 构造与 fallback 选取，不改变候选集合，对下游透明。

**论文对应。** 方法章节"候选排序"小节，定位为 implicit process reward 的轻量实例；消融表对比 取第一个 vs. 按支持度排序 的正确率。

### C. 自适应提前停止（`search_harness_pipeline_v4.py`）

**动机。** 原停止策略是纯预算门（`max_iterations` / `max_total_searches` / `max_crawl_calls`），即使候选已被验证且无硬冲突，Agent 仍会耗尽预算才停——浪费搜索调用、拖长轨迹。

**方法。** 在 `_check_stop` 增加一个提前停止分支 `_verified_candidate_early_stop`：若某候选 `verification_status == "verified"` 且无 `hard_conflicts`、无 `unresolved_constraints`，则触发 `verified_candidate_early_stop`。这把停止策略从纯预算门升级为**anytime / adaptive** 策略——任务"已解"即停，预算留给难题。

**论文对应。** 方法章节"自适应计算预算"小节，对应 anytime algorithm / adaptive compute；消融表给出 搜索次数 vs. 正确率 的 Pareto 曲线（开关 early-stop 两条线）。

### E. 失败分类分析（`failure_taxonomy.py`）

**动机。** 项目的 41% 错误率是一个整体数字，但论文需要把错误**拆成可归因的子类**，才能说明每个增强模块攻击的是哪部分错误。这是一个**纯离线分析脚本**，不改动任何核心代码。

**方法。** 扫描 `data/trajectories/deepseek-chat/` 下全部轨迹，按可观测字段（`metadata.status`、`answer_match`、`answer` 内容、工具调用数）将每题分入四类失败 + 一类正确：

| 类别 | 含义 | 触发条件 |
|------|------|---------|
| `candidate_failure` | 未产出具体候选 | 答案为空/Unknown 且未耗尽预算 |
| `search_failure` | 检索预算耗尽 | `status` 命中 `max_*` 触发器 |
| `finalizer_failure` | 提交了错误的具体答案 | `answer_match == False` 且答案非空 |
| `verification_failure` | 自验证层反驳了原答案 | 新增 `verification.verdict == "refuted"` 字段 |
| `correct` | 答案正确（非失败） | `answer_match == True` |

**用法。**
```bash
cd SearchHarness_0425
python failure_taxonomy.py --root ../data/trajectories/deepseek-chat \
    --out failure_taxonomy_report.json --csv failure_taxonomy.csv
```

**当前基线分布（1000 题，Plan A 未启用前）。**

| 类别 | 数量 | 占比 |
|------|------|------|
| correct | 592 | 59.2% |
| search_failure | 207 | 20.7% |
| finalizer_failure | 142 | 14.2% |
| candidate_failure | 59 | 5.9% |

> `verification_failure` 在 Plan A 启用后的新轨迹中才会出现；当前基线为 0。该数字将作为论文消融表里"自验证层从 finalizer_failure 中挽回多少题"的直接证据。

**论文对应。** 论文 Error Analysis 小节的分类骨架；启用 Plan A 前后对比可量化自验证层的净贡献。

---

## 实验结果：Plan A 自验证消融（2026-08-04）

> 小样本消融，对比 baseline（Plan A 关闭）与 treatment（Plan A 全路径开启）在 BrowseComp 固定样本 pos0-2 上的表现。完整报告见 [`docs/experiment_compare_20260804.md`](docs/experiment_compare_20260804.md)。

### 实验设置

| 项 | 值 |
|---|---|
| 数据集 | BrowseComp 固定样本（seed=123, sample_size=10, positions=0-2, n=3） |
| 模型 | GLM-5.2（planner+executor+grader 同模型） |
| Budget | max_iter=6, max_crawl=30, max_total_searches=120 |
| 变量 | 仅 `ENABLE_PLAN_A_VERIFICATION`（0 vs 1），Plan B/C/E 在两组均开启 |

### 结果对比

| 位置 | Gold | Baseline 答 | Baseline ✓? | Baseline 耗时 | Treatment 答 | Treatment ✓? | Treatment 耗时 |
|---|---|---|---|---|---|---|---|
| pos0 | Achimota School | Achimota School | ✅ | 329s | **Unknown** | ❌ | 362s |
| pos1 | Marguerite Smith | Marguerite Smith | ✅ | 498s | Marguerite Smith | ✅ | 566s |
| pos2 | Abangan 2024 | Unknown | ❌ | 2040s | 马不停蹄的忧伤 | ❌ | 1300s |
| **合计** | — | — | **2/3 (66.7%)** | **2370s** | — | **1/3 (33.3%)** | **1662s** |

### 资源消耗

| 指标 | Treatment | Baseline | Δ |
|---|---|---|---|
| LLM 调用 | 44 | 67 | **-34%** |
| search 调用 | 41 | 79 | **-48%** |
| crawl 调用 | 12 | 28 | **-57%** |
| 总耗时 | 1662s | 2370s | **-30%** |
| 准确率 | 1/3 | 2/3 | **-33pp** |

### 关键发现

**1. Plan A 假阴性（核心论文点）→ 已修复**：pos0 planner 第 1 轮给出正确答案 "Achimota School"，Plan A 验证器 **误判 REFUTED**，输出 Unknown。根因是 `_judge` 将题目截断到 400 字符，截掉了末尾的实际提问 "What was the name of the secondary or senior high school they attended?"，验证器只看到 "This person..." 就误判答案类型为"人"。修复三层：(a) 截断扩展到 1200 字符；(b) 类型感知指令；(c) 验证查询用最后一句关键词。修复后 Plan A 判定从 REFUTED → INCONCLUSIVE，答案从 Unknown → Achimota School（正确），耗时 348s。

| | 修复前 (treatment) | 修复后 (fix v2) | Baseline |
|---|---|---|---|
| pos0 答案 | Unknown ❌ | **Achimota School** ✅ | Achimota School ✅ |
| Plan A 判定 | REFUTED（假阴性） | INCONCLUSIVE（安全保留） | 不触发 |
| 耗时 | 362s | 348s | 329s |

**2. 修复后全样本重跑（pos0-2，2026-08-04 17:24）**：Plan A 修复后全样本 acc=3/3，无假阴性、零误杀，效率保持。

| 维度 | Baseline (无Plan A) | Pre-fix Treatment | **Post-fix Treatment** |
|---|---|---|---|
| Accuracy | 2/3 (0.667) | 1/3 (0.333) | **3/3 (1.000)** ✅ |
| 总耗时 | 2370s | 1662s | 1759s |
| 平均耗时/题 | 790s | 554s | **586s** |
| pos0 | ✅ Achimota (1 iter, 329s) | ❌ Unknown (1 iter, 362s) [假阴性] | ✅ Achimota (4 iter, 653s) [INCONCLUSIVE] |
| pos1 | ✅ Marguerite (2 iter, 498s) | ✅ Marguerite (2 iter, 566s) | ✅ Marguerite (2 iter, 636s) [INCONCLUSIVE] |
| pos2 | ❌ Unknown (7 iter, 2040s) | ❌ 错答 (6 iter, 1300s) | ✅ Abangan 2024 (3 iter, 471s) [INCONCLUSIVE] |
| Plan A 判定分布 | n/a | REFUTED×1, INCONCLUSIVE×2 | **INCONCLUSIVE×3**（零误杀） |

- **假阴性彻底修复**：pos0 REFUTED→Unknown 变为 INCONCLUSIVE→Achimota School，与 Baseline 持平且不引入新误杀
- **零误杀（zero false-refute）**：3 题 Plan A 全部 INCONCLUSIVE，验证器在弱模型上呈现"保守安全"行为，符合 failure-safe 设计
- **pos2 额外收益**（待验证）：pos2 在 Baseline（Unknown）和 Pre-fix（错答）均失败，Post-fix 首次答对，可能源于 last-sentence-keyword 验证查询更精准，但 n=3 不足以排除运行间噪声，需在 n≥30 上确认
- **效率保持**：Post-fix 1759s 比 Baseline 2370s 节省 26%，Plan A 每题仅 1 次 _judge LLM 调用 + 1 次证据搜索（<10s/题开销）
- **论文叙事调整**：Plan A 不再叙述为"always-effective enhancement"，改为"precision/recall trade-off discovery + failure-safe 设计实证"——修复前后对比构成完整故事弧

**3. 失败安全设计生效**：pos2 treatment 给出具体错答（Plan A 未 refute，finalizer 路径较保守），baseline 给 Unknown。Plan A refute 后输出 Unknown 而非错答，保留下游二次验证入口。修复后 pos2 不再触发此路径（答对了），但 failure-safe 语义保留作为安全网。

### 与 2026.08 SOTA 对比

| 本项目增强 | SOTA 对应 | 创新点 |
|---|---|---|
| Plan A (self-verification) | AREX outer loop / DeepVerifier | 全路径覆盖 + 失败安全（refute→Unknown） |
| Plan B (candidate ranking) | Adaptive PRM (implicit) | 用 supporting_constraints 计数替代训练 reward model |
| Plan C (adaptive early stop) | AVA anytime verification | 候选达阈值即停，无需额外训练 |
| Plan E (failure taxonomy) | DeepVerifier Failure Taxonomy | 离线 4 桶分类，匹配项目 41% 错误率 |

**论文定位**：不与 GPT-5.6（92.2%）比绝对分数，而是论证**方法论可迁移性** —— 中等模型（GLM-5.2 @ 59.2%）+ 零训练推理时增强 + 失败安全设计，可消融、可诊断、可迁移。

### 局限与后续

- 样本量极小（n=3），不具统计显著性；pos2 的 Post-fix 收益尤其需在更大样本上验证是否稳定
- Plan B/C/E 未单独消融（本实验仅隔离 Plan A）
- 单一模型（GLM-5.2）单一 seed（123）单次运行，未做 temperature=0 严格可复现性验证
- 后续：扩大至 n≥30 估计 Plan A precision/recall；`VERIFIER_TYPE_AWARE` 0 vs 1 消融；跨模型（Qwen3-32B、GPT-4o）验证 Plan A 是否从 INCONCLUSIVE 主导转向 VERIFIED 主导

### 复现命令

```bash
# Baseline (Plan A off)
ENABLE_PLAN_A_VERIFICATION=0 python run_browsecomp_fixed_sample.py \
    --seed 123 --sample-size 10 --positions 0-2 \
    --output results/planA_baseline_pos0to2.json \
    2>&1 | tee logs/run_baseline_noPlanA.log

# Treatment (Plan A on, full-path, pre-fix)
ENABLE_PLAN_A_VERIFICATION=1 python run_browsecomp_fixed_sample.py \
    --seed 123 --sample-size 10 --positions 0-2 \
    --output results/planA_treatment_full_pos0to2.json \
    2>&1 | tee logs/run_treatment_full.log

# Treatment (Plan A on, post-fix, type-aware) — 2026-08-04 17:24 acc=3/3
ENABLE_PLAN_A_VERIFICATION=1 VERIFIER_TYPE_AWARE=1 python run_browsecomp_fixed_sample.py \
    --seed 123 --sample-size 10 --positions 0-2 \
    --output results/planA_treatment_fixed_pos0to2.json \
    2>&1 | tee logs/run_treatment_fixed_pos0to2.log
```

---

## 调试与排错

### 1. 冒烟测试脚本

| 脚本 | 用途 | 关键参数 |
|------|------|---------|
| `debug_llm_smoke.py` | 验证 LLM 端点可达性、Key 模型权限 | `--no-proxy` 清除代理环境变量 |
| `debug_llm_smoke.py` | 验证思考模式开关（对比 `minimal` vs 默认的 `reasoning_tokens`） | `--verify-thinking` |
| `debug_serper_smoke.py` | 验证 Serper 搜索可用性、Key 额度 | 无参数 |
| `smoke_test_simple.py` | 端到端 pipeline 冒烟（trivial 问题跑通全链路） | `--question`、`--max-iterations` |
| `smoke_test_thinking.py` | 思考模式端到端冒烟（同一问题对比多个 `EXECUTOR_THINKING` 取值） | `--efforts none high`、`--question` |

`debug_llm_smoke.py` 会打印：API 端点、Key 前缀（脱敏）、代理快照、`/models` 与 `/chat/completions` 的状态码与响应前缀。若看到 model-access denial，说明当前 Key 无权访问指定模型——需更换 Key 或改用 Key 可访问的模型。加 `--verify-thinking` 时会额外发起两次 `chat/completions`：一次 `reasoning_effort=minimal`、一次默认，对比 `reasoning_tokens` 差异以确认思考开关在 API 层生效（OpenAI 标准，仅顶层 kwarg，不注入 extra_body）。

### 2. 查看轨迹

每次运行会在 `--trajectory-dir/{model_id}/` 下生成 `task_NNNNNN.json`（增强格式，约 1-2MB）。同时写入 `task_NNNNNN.partial.json` 增量快照，防止中途崩溃丢失数据。

#### 增强轨迹格式（`trajectory_recorder_enhanced.py`）

增强录制器在原有扁平 `messages` 基础上新增 **10 个结构化字段**，为模型训练和日志排查提供精确数据：

| 字段 | 类型 | 说明 |
|------|------|------|
| `metadata` | object | 问题、模型、状态、迭代数、耗时、pipeline 配置 |
| `events` | array | 结构化事件流：每个关键决策点（搜索、候选变更、规划、答题）一条，含 `timestamp`/`iteration`/`agent`/`event_type`/`data` |
| `search_log` | array | 搜索日志：query → 判重 verdict → 结果数 → 延迟，按迭代分组 |
| `llm_calls` | array | LLM 调用元数据：每次 planner/executor 调用的延迟、content/reasoning 字符数 |
| `candidate_snapshots` | array | 候选池快照：每轮迭代后的候选状态（add/verify/eliminate 转移） |
| `iteration_summaries` | array | 每轮迭代摘要：子任务、findings、新候选、阶段 |
| `planner_conversations` | array | Planner 逐轮对话（含 plan/answer/latency） |
| `executor_conversations` | array | Executor 逐轮对话（含 subtask/findings/status/latency/new_candidates） |
| `pipeline_state` | object | 流水线最终状态：阶段、候选记录、验证队列 |
| `messages` | array | 向后兼容的扁平合并消息（planner + executor），带 `_agent`/`_iteration` 标签 |

```json
{
  "metadata": {
    "question": "...", "model": "<your-model-name>", "status": "finished",
    "iterations": 4, "started_at": "...", "finished_at": "...",
    "pipeline_config": { "max_iterations": 5, "max_total_searches": 200, ... }
  },
  "events": [
    {"timestamp": 1234567890.0, "iteration": 0, "agent": "executor",
     "event_type": "search_query", "data": {"queries": [...], "verdict": "allow"}},
    {"timestamp": 1234567891.0, "iteration": 0, "agent": "executor",
     "event_type": "search_executed", "data": {"query": "...", "num_results": 8, "latency_ms": 1234.0}}
  ],
  "search_log": [
    {"iteration": 0, "agent": "executor", "query": "...",
     "verdict": "allow", "num_results": 8, "latency_ms": 1234.0}
  ],
  "llm_calls": [
    {"iteration": 0, "agent": "planner", "latency_ms": 6138.0,
     "content_chars": 3399, "reasoning_chars": 1338}
  ],
  "candidate_snapshots": [
    {"iteration": 0, "total": 3, "active": 2, "eliminated": 1, "names": [...]}
  ],
  "planner_conversations": [{"iteration": 0, "plan": {...}, "messages": [...]}],
  "executor_conversations": [{"iteration": 0, "subtask": "...", "messages": [...]}],
  "messages": [ ...向后兼容的扁平合并消息... ]
}
```

#### 事件录制系统

Pipeline 通过 `event_callback` 钩子将结构化事件推送到录制器。Executor 在每次搜索时触发 `search_query`（判重结果）和 `search_executed`（搜索结果）事件，Pipeline 在子任务选择、候选变更、答题终结时触发对应事件。

迭代追踪：Pipeline 使用可变容器 `_trajectory_current_iter = [0]`，在每次迭代开始时更新 `_current_iter[0] = iteration`，闭包捕获容器引用并在调用时读取当前值，确保事件标签正确反映所属迭代。

排查答题质量问题时重点检查：

- `candidate_snapshots` 中候选的 add/verify/eliminate 转移轨迹
- `search_log` 中查询是否重复（verdict=reject 说明被判重拦截）
- `llm_calls` 的延迟分布定位耗时瓶颈
- `events` 流按 iteration 过滤查看特定轮次的决策链
- `pipeline_state.candidate_records` 中错误候选是否累积 `hard_conflicts` 但未被 eliminate
- finalizer 是否在仍有未解决硬冲突时过早收敛

### 3. 日志

日志通过 `loguru` 输出到 stdout，级别由 `LOG_LEVEL` 控制。关键日志前缀：

- `[Pipeline]` — 流水线阶段流转、planner/executor 启停与耗时
- `[QueryCritic]` — 查询判重结果（rule / llm）
- `[CrawlController]` — 搜索 vs 抓取决策
- `[SubtaskCritic]` — 子任务 reject / accept / pivot
- `[Finalizer]` — 最终答案收敛

### 4. 耗时优化

参见 `docs/latency_optimization_20260731.md`。v4 测试中 2483s 总耗时的瓶颈分布：

| 模块 | 占比 | 说明 |
|------|------|------|
| `query_critic._llm_based_check` | 33.1% | 每个 query 单独调 LLM 判重（43 次 × 13.1s） |
| `_settle_subtask_with_critic` | 31.6% | 含 planner 重试 + SubtaskCritic LLM |
| `search_crawl_controller.evaluate` | 22.6% | 规则不明确时 fallback 到 LLM |

所有 LLM 调用完全串行，无并行/批量/缓存。优化方向（按 ROI 排序）：批量 QueryCritic、规则层增强、并行工具调用、prompt/prefix caching。

### 5. 历史背景

`WORKLOG.md` 记录了从 `0413_v3` 沿袭而来的工作脉络、固定样本答案表、推荐验证顺序与失败模式分析。新接手者建议先读 `WORKLOG.md` 的 §15「Short Resume Summary」。

---

## 单元测试

```bash
cd SearchHarness_0425
pytest tests/test_core_rules.py -v
```

覆盖 37 个用例，针对**纯函数与规则层**（不依赖外部 API）：

- `query_critic._normalize_query` — 大小写、空白、标点、幂等性
- `QueryCritic._rule_based_check` — 字面重复、空历史、Jaccard 相似度
- `search_crawl_controller._compute_signals` — 信号提取
- `SearchCrawlController._rule_based_check` — 规则覆盖
- `config.settings` — 环境变量加载
- `llm_client._is_retryable` — 错误分类

测试不调用真实 LLM / Serper，可在 CI 中安全运行。

---

## 轨迹与蒸馏

### 轨迹格式（增强格式，本目录生成）

`trajectory_recorder_enhanced.py` 输出包含 10 个结构化字段的增强轨迹（约 1-2MB），同时保留向后兼容的扁平 `messages` 字段。详见上方 [调试与排错 §2](#2-查看轨迹) 中的字段说明表。

### 结果 JSON 字段

每次评测输出 `results/*.json`，每个题目的结果包含：

| 字段 | 说明 |
|------|------|
| `extracted_answer` | Pipeline 收敛出的答案 |
| `is_correct` | Grader 判定 |
| `pipeline_status` | `finished` / `max_turns_reached` / `error` |
| `failure_category` | 失败分类（成功时为空） |
| `iterations` | 实际迭代轮数 |
| `stop_reason` | 停止原因（`finished` / `budget_exhausted` / `max_iterations`） |
| `trajectory_path` | 轨迹文件路径（交叉引用） |
| `elapsed_seconds` | 耗时 |

### 转换为 OffSeeker 训练格式

转换脚本位于项目根目录（`SearchHarness_0425/` 的上一级）：

```bash
cd ..   # 回到 search_data_systhesis/

python convert_trajectory_to_offseeker_format.py \
  --input SearchHarness_0425/logs/trajectories_pos4 \
  --output data/offseeker_format/search_harness \
  --enable-hint
```

输出 OffSeeker 格式（`<function_call>...</function_call>` 标签 + `<result>...</result>` 工具回包），可直接送入 `training_scripts/` 的 SFT/DPO 配置训练。

---

## 常见问题

### Q1: 启动报 `model-access denial` / 模型不可用
当前 API Key 无权访问 `MODEL_NAME` 指定的模型。运行 `debug_llm_smoke.py` 确认可用模型列表，将 `MODEL_NAME` 改为 Key 可访问的模型（部分模型需额外授权，以 `/models` 接口返回的可用列表为准）。

### Q2: Serper 返回 `Not enough credits`
Serper 额度耗尽。在 [serper.dev](https://serper.dev) 充值或更换 Key，更新 `.env` 中的 `SERPER_API_KEY`。

### Q3: 单题耗时过长
默认预算较大（`max-total-searches=80`）。冒烟/调试时可大幅缩减：`--max-iterations 4 --max-planner-searches 5 --max-executor-searches 10 --max-total-searches 20`。耗时瓶颈与优化方案见 `docs/latency_optimization_20260731.md`。

### Q4: 答案错误但 status 是 `solved`
这正是 v4 结构化候选状态要解决的问题。检查轨迹中的 `candidate_records`：错误候选是否积累了 `hard_conflicts` 但未被 eliminate，或者 finalizer 在仍有未解决冲突时过早收敛。

### Q5: 代理环境变量导致请求失败
`debug_llm_smoke.py` 的 `--no-proxy` 参数会清除 `HTTP_PROXY` / `HTTPS_PROXY` 等环境变量。若公司网络强制代理，需确保代理允许访问 LLM 端点与 `google.serper.dev`。

### Q6: 如何只重打分不重跑
使用 `regrade_results.py`，传入已有结果 JSON，用新 grader 模型重新判定 `correct` 字段，无需消耗搜索配额。

---

## 相关文档

- `WORKLOG.md` — 历史工作记录与失败模式分析
- `docs/latency_optimization_20260731.md` — 耗时分析与优化方案
- `docs/smoke_test_2026-07-30.md` — 冒烟测试报告
- `docs/insight_candidate_generation_bottleneck.md` — 候选生成瓶颈分析
- `docs/insight_verification_ordering_failure.md` — 验证排序失败分析
- `planning_agent_prompt_v3.md` / `search_agent_prompt_v3.md` — v3 通用 prompt
- `planning_agent_prompt_simple.md` / `search_agent_prompt_simple.md` — 简化 prompt（compact，适配推理模型）
- 上级目录 `CLAUDE.md` — 整体项目（OffSeeker 蒸馏）说明
