# SearchHarness 行业对标与能力差距分析

> **版本**：v1.0 · 2026-08-20
> **定位**：横向对标业界成熟的评测/Agent harness，识别 SearchHarness 的**能力维度**缺口（工程结构与资产治理问题见 [`PROJECT_STRUCTURE_PLAN.md`](./PROJECT_STRUCTURE_PLAN.md)，代码层模块化设计见 [`REFACTOR_DESIGN.md`](./REFACTOR_DESIGN.md)，统一优先级归口见 [`ROADMAP.md`](./ROADMAP.md)）。
> **核实方式**：本文全部"现状"列均通过对代码库的实测确认（grep / 文件枚举），非凭印象。

---

## 1. 对标对象与各自的核心武器

| Harness | 背景 | 值得借鉴的核心能力 |
|---|---|---|
| **Inspect AI** | UK AISI，agent 评测事实标杆 | Task/Solver/Scorer/Sandbox 四层抽象；eval 级 resume/retry；per-model usage 成本追踪；LLM 与工具响应缓存；per-provider 并发信号量；结构化的 `.eval` 结果格式 |
| **OpenAI simple-evals / Evals** | BrowseComp 官方评测器 | registry 注册多基准；统一 grader 模板；sampler 与 eval 逻辑分离 |
| **EleutherAI lm-evaluation-harness** | LLM 评测社区标准 | task registry（YAML 声明式注册新基准）；请求/响应磁盘缓存保证重放一致；置信区间等聚合统计内建 |
| **LangGraph / OpenDeepResearch** | deep research agent 工程框架 | checkpointer（durable execution，断点续跑）；LangSmith 全链路追踪；HITL 中断 |
| **SWE-bench / WebArena** | agentic 任务评测 | docker 锁定执行环境，逐样本可重放；确定性 seed 贯穿全链路 |
| **HELM** | 学术评测框架 | scenario → metric 流水线；标准化 results schema + run spec（每次运行的完整配置可追溯） |

## 2. 能力差距矩阵

> 优先级口径：**P0** = 立刻止血/没有它别的重构不安全；**P1** = 一个月内应补；**P2** = 季度内；**P3** = 暂缓。

| # | 维度 | 行业做法 | SearchHarness 现状（实测） | 级别 |
|---|---|---|---|---|
| G1 | **Benchmark 抽象** | task/solver/scorer registry，YAML/装饰器注册新基准即插即用 | 硬编码 BrowseComp 单数据集，`run_browsecomp*` 入口与数据集名耦合 | **P0** |
| G2 | **Checkpoint / Resume** | eval 级断点续跑（Inspect `resume`，LangGraph checkpointer）；样本粒度的幂等重试 | ❌ 全库 grep 无 resume/checkpoint 痕迹；长 run 中断 = 全部丢弃。注意：上级仓库 `batch_generate_trajectories.py` 已有成熟的 metadata 断点续跑实现可借鉴 | **P0** |
| G3 | **成本与配额追踪** | 每 run 记录 token usage 与估算成本（Inspect usage、HELM cost） | ❌ `llm_client.py` 无任何 usage/成本统计；只有重试与退避 | **P0** |
| G4 | **可复现性** | LLM 响应磁盘缓存 + seed 贯穿全链路 + 环境锁定（docker/lockfile） | seed 仅用于数据集**抽样**（`_load_fixed_sample`），不进 LLM 请求；仅 crawl controller 有一个内存决策缓存，无 LLM/HTTP 响应缓存；无 Dockerfile/lockfile | **P0** |
| G5 | **代码执行沙箱** | docker/gVisor/e2b 隔离 + 网络/资源管控（Inspect sandbox provider、SWE-bench） | `tools/subprocess_interpreter.py` 裸 `subprocess.Popen`，无隔离、无网络管控 | **P1** |
| G6 | **异步执行模型** | asyncio-native + per-provider 并发上限（Inspect `max_connections`） | 纯 `ThreadPoolExecutor`，worker 数硬编码散落在 6+ 处（4/5/8） | **P1** |
| G7 | **结构化观测** | span 级 tracing（OTEL / Langfuse / LangSmith / OpenAI Agents SDK），单任务时间线可视化 | loguru 日志 + trajectory JSON；无 span、无延迟分解视图（latency 分析靠事后人工写的报告） | **P1** |
| G8 | **评估统计严谨性** | 置信区间 / bootstrap / 显著性检验（HELM、lm-eval 内建） | 只有裸 accuracy（`regrade_results.py` 单行计算）；`run_seed_repeats` 有重复实验能力但无方差聚合与显著性判断 | **P1** |
| G9 | **评判器（grader）校准** | grader 与人工标注算 agreement；grader 模板与官方对齐并可版本化 | `answer_verifier.py` LLM 判分无人工校准基线；regrade 靠手工脚本 | **P1** |
| G10 | **统一结果模式** | 标准化 results schema + run spec（HELM run_specs、Inspect `.eval` 文件，配置/结果一体可追溯） | `results/` 散装 JSON，无统一 schema；3 个文件与 gitignore 规则冲突仍被跟踪 | **P2** |
| G11 | **分布式执行** | 队列/多机 worker 横向扩展 | 单机多线程 | **P2** |
| G12 | **Guardrails / 安全护栏** | 工具调用与内容安全护栏（OpenAI Agents SDK guardrails、Inspect 的 content limits） | ❌ 无 | **P2** |

## 3. 已达标 / 差异化优势（不需要补的部分）

| 能力 | 说明 |
|---|---|
| ✅ 限流与重试 | 429 识别 + 指数退避（`llm_client.py`、`llm_error_utils.py`），与行业持平 |
| ✅ 预算控制 | pipeline 内建搜索预算与有界停止（多家 harness 只做 max_turns） |
| ✅ 多模型 profile | `model_profiles.yaml` 声明式模型配置，接近 lm-eval 的 model args |
| ✅ 失败分类学 | `failure_taxonomy.py` 的失败归因粒度超过 simple-evals |
| ✅ 轨迹录制 + 蒸馏导出 | **差异化优势**：Inspect/lm-eval 均不产出可直接蒸馏的轨迹，这是本项目的核心资产 |
| ✅ 单测规模 | 214 个 pytest 用例（缺 CI 门禁，属结构层 P0） |
| ✅ Critic 体系 | query/subtask/direction 三层 critic + 规则优先/LLM 兜底裁决，优于多数开源 harness |

## 4. 结论

1. **P0 四件套**：G2 resume（中断=白跑，止血第一优先）→ G3 cost 追踪（并发烧钱不可测）→ G4 缓存+seed 全链路（实验对比失去意义之前必须固定）→ G1 benchmark 抽象（后续所有评测扩展的地基）。
2. **G5 沙箱是安全红线**，P1 中最高优先；G8/G9 直接影响实验结论的可信度（论文级要求）。
3. 差距集中在"评测基础设施成熟度"，**不在 agent 算法层**——agent 侧（critic 体系、预算控制、轨迹资产）反而领先多数开源 harness。
