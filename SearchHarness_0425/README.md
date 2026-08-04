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
| `deepseek_thinking_compat.py` | 推理模型流式兼容层：处理 `reasoning_content` 字段、思考预算（`LLM_THINKING_BUDGET_TOKENS`）、工具调用流式解析 |
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
├── deepseek_thinking_compat.py       # 推理模型流式兼容层（reasoning_content + 思考预算）
├── run_browsecomp.py                 # 全量评测入口
├── run_browsecomp_fixed_sample.py    # 固定样本评测入口
├── run_seed_repeats.py               # 重复运行
├── regrade_results.py                # 结果重打分
├── build_seed123_k10_full.py         # 重建固定子集
├── debug_deepseek_smoke.py           # LLM 端点冒烟测试
├── debug_serper_smoke.py             # Serper 搜索冒烟测试
├── planning_agent_prompt_v3.md / search_agent_prompt_v3.md     # v3 通用 prompt
├── planning_agent_prompt_glm.md / search_agent_prompt_glm.md  # GLM 专用 prompt
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

# 主模型（默认 GLM-5.2）
MODEL_NAME=GLM-5.2
# 执行 Agent 模型（留空则回退到 MODEL_NAME）
EXECUTOR_MODEL_NAME=GLM-5.2

# LLM 超时与思考预算
LLM_TIMEOUT_S=600
LLM_THINKING_BUDGET_TOKENS=1000

# ── Grader（可选，缺省回退到主 LLM）──
GRADER_API_BASE=https://your-grader-endpoint/v1
GRADER_API_KEY=sk-yyyyyyyyyyyyyyyy
GRADER_MODEL_NAME=deepseek-chat

# ── 搜索工具（必需）──
SERPER_API_KEY=your_serper_key
JINA_API_KEY=your_jina_key
CRAWLER_ENGINE=jina                 # 或 html2text

# ── 日志与 prompt 模式 ──
LOG_LEVEL=INFO
PLANNER_SIMPLE_PROMPT=false
EXECUTOR_SIMPLE_PROMPT=false
```

> **重要**：`MODEL_NAME` 必须是当前 API Key 可访问的模型。冒烟测试显示部分 Key 可访问 `GLM-5.2` 但无法访问 `deepseek-chat`，模型权限错误不会在启动时暴露，只在调用时返回 model-access denial。

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
| `MODEL_NAME` | `GLM-5.2` | 主模型 ID |
| `EXECUTOR_MODEL_NAME` | 回退到 `MODEL_NAME` | 执行 Agent 模型 |
| `LLM_TIMEOUT_S` | `600` | 单次 LLM 调用超时（秒） |
| `LLM_THINKING_BUDGET_TOKENS` | `1000` | 思考预算 token |
| `GRADER_API_BASE` / `GRADER_API_KEY` / `GRADER_MODEL_NAME` | 回退到主 LLM | Grader 配置 |
| `SERPER_API_KEY` | — | Google 搜索 Key |
| `JINA_API_KEY` | — | Jina 抓取 Key |
| `CRAWLER_ENGINE` | `jina` | 抓取引擎：`jina` 或 `html2text` |
| `LOG_LEVEL` | `INFO` | loguru 日志级别 |
| `PLANNER_SIMPLE_PROMPT` | `false` | 使用简化 planner prompt |
| `EXECUTOR_SIMPLE_PROMPT` | `false` | 使用简化 executor prompt |

---

## 快速开始

### 冒烟测试（强烈建议首次运行先做）

依次验证 LLM 端点与 Serper 搜索是否可用：

```bash
cd SearchHarness_0425

# 1. LLM 端点冒烟测试（检查 /models 与 /chat/completions）
python3 debug_deepseek_smoke.py --no-proxy

# 2. Serper 搜索冒烟测试
python3 debug_serper_smoke.py
```

预期输出：两个脚本均打印 `status_code: 200` 并返回正常结果。若 Serper 返回 `{"message":"Not enough credits","statusCode":400}`，说明额度耗尽，需充值或更换 Key。

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

> **推理模型提示**：使用 GLM-5.2 等推理模型时，设置 `LLM_THINKING_BUDGET_TOKENS`（如 `4096`）可让模型充分推理后再决策。默认 `1000` 对复杂多跳问题可能不足，导致规划过浅。设置方法：在 `.env` 中配置或运行时前缀 `LLM_THINKING_BUDGET_TOKENS=4096 python3 run_browsecomp_fixed_sample.py ...`。

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

## 调试与排错

### 1. 冒烟测试脚本

| 脚本 | 用途 | 关键参数 |
|------|------|---------|
| `debug_deepseek_smoke.py` | 验证 LLM 端点可达性、Key 模型权限 | `--no-proxy` 清除代理环境变量 |
| `debug_serper_smoke.py` | 验证 Serper 搜索可用性、Key 额度 | 无参数 |

`debug_deepseek_smoke.py` 会打印：API 端点、Key 前缀（脱敏）、代理快照、`/models` 与 `/chat/completions` 的状态码与响应前缀。若看到 model-access denial，说明当前 Key 无权访问指定模型——需更换 Key 或改用 `GLM-5.2`。

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
    "question": "...", "model": "GLM-5.2", "status": "finished",
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
当前 API Key 无权访问 `MODEL_NAME` 指定的模型。运行 `debug_deepseek_smoke.py` 确认可用模型列表，将 `MODEL_NAME` 改为 Key 可访问的模型（实测 `GLM-5.2` 通常可用，`deepseek-chat` 需额外授权）。

### Q2: Serper 返回 `Not enough credits`
Serper 额度耗尽。在 [serper.dev](https://serper.dev) 充值或更换 Key，更新 `.env` 中的 `SERPER_API_KEY`。

### Q3: 单题耗时过长
默认预算较大（`max-total-searches=80`）。冒烟/调试时可大幅缩减：`--max-iterations 4 --max-planner-searches 5 --max-executor-searches 10 --max-total-searches 20`。耗时瓶颈与优化方案见 `docs/latency_optimization_20260731.md`。

### Q4: 答案错误但 status 是 `solved`
这正是 v4 结构化候选状态要解决的问题。检查轨迹中的 `candidate_records`：错误候选是否积累了 `hard_conflicts` 但未被 eliminate，或者 finalizer 在仍有未解决冲突时过早收敛。

### Q5: 代理环境变量导致请求失败
`debug_deepseek_smoke.py` 的 `--no-proxy` 参数会清除 `HTTP_PROXY` / `HTTPS_PROXY` 等环境变量。若公司网络强制代理，需确保代理允许访问 LLM 端点与 `google.serper.dev`。

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
- `planning_agent_prompt_glm.md` / `search_agent_prompt_glm.md` — GLM 专用 prompt
- 上级目录 `CLAUDE.md` — 整体项目（OffSeeker 蒸馏）说明
