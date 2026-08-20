# SearchHarness 项目结构整理与规划

> **版本**：v1.0 · 2026-08-20
> **定位**：本文是 [`REFACTOR_DESIGN.md`](./REFACTOR_DESIGN.md)（v1.0 · 2026-08-19）的**姊妹篇与执行配套文档**。
> **总入口**：统一问题清单与优先级（合并本文/REFACTOR_DESIGN/GAP_ANALYSIS）见 [`ROADMAP.md`](./ROADMAP.md)；行业对标见 [`GAP_ANALYSIS.md`](./GAP_ANALYSIS.md)。
> `REFACTOR_DESIGN.md` 聚焦"代码层的模块化改造设计"（god-object 拆分、契约层、LLM 层规整、逐方法映射），本文聚焦"**项目级的结构盘点、资产治理与迁移编排**"：文件全量归类、非代码资产（logs/results/docs/数据文件）归宿、业界实践对标（按指定基准）、分阶段执行计划与检查点。
> 两份文档共用同一目标结构与同一套 step 编号；**凡 `REFACTOR_DESIGN.md` 已写透的细节（方法→模块映射表、contract 字段表、LLM 层 import 替换表），本文只引用不重复**。
> **验证基线（本文撰写时实测）**：`python -m pytest tests/ -q` → **214 passed in 16.72s** ✅（与 REFACTOR_DESIGN 基线一致）

---

## 目录

- [1. 执行摘要](#1-执行摘要)
- [2. 现状全景盘点（实测）](#2-现状全景盘点实测)
- [3. 按关注点的文件归类](#3-按关注点的文件归类)
- [4. 结构问题诊断](#4-结构问题诊断)
- [5. 业界成熟方案对标](#5-业界成熟方案对标)
- [6. 目标结构](#6-目标结构)
- [7. 全量文件映射表](#7-全量文件映射表)
- [8. 分阶段迁移计划](#8-分阶段迁移计划)
- [9. import 兼容与 git 历史保留策略](#9-import-兼容与-git-历史保留策略)
- [10. 风险清单与缓解](#10-风险清单与缓解)
- [附录 A：当前基线实测数据](#附录-a当前基线实测数据)
- [附录 B：统一验证命令集](#附录-b统一验证命令集)

---

## 1. 执行摘要

SearchHarness_0425 是一个多智能体 Web 搜索评测框架（Planner → Executor → Critics → Finalizer 循环编排，BrowseComp 数据集评测 + 蒸馏轨迹录制）。**代码领域的依赖拓扑本身是健康的**（无循环依赖，pipeline → agents → memory/tools → llm 基建方向基本单向），问题集中在**物理组织与资产治理**：

1. **根目录扁平混杂 34 个裸名模块**（14,613 行），库、入口、脚本、prompt、配置、数据混放一层；
2. **34 个文件靠 `sys.path` hack 互相裸名导入**（实测 12 处 `sys.path.insert`，其中 8 个库文件把**父目录** `search_data_systhesis/` 塞进路径，比预想的更激进）；
3. **版本演化管理失序**：`_v3/_v4/_enhanced/_compat` 后缀固化在文件名里，双 trajectory recorder 分叉 557 行重复；
4. **非代码资产无治理**：`logs/` 已累积 **955MB / 354 个目录**、3 个 `results/*.json` 在 gitignore 生效前已被 git 跟踪、根目录躺着 272KB 孤儿产物 `failure_taxonomy_report.json`、`docs/` 混放设计文档与 13 份一次性实验报告和 6 个数据文件；
5. **git 卫生阻碍重构启动**：`tools/`（vendored，1,644 行）与 `tests/__init__.py` **尚未提交**、6 个文件带未提交改动、当前实际在 `test` 分支而 REFACTOR_DESIGN 以 `master` 为基线、且**全仓库无任何 tag**。

目标结构一句话：**`src/search_harness/` 单包（contract/config/llm/memory/tools/agents/trajectory/pipeline/eval/cli 十一个子包）+ `scripts/{run,smoke,analysis}` + `data/` + `docs/{experiments}` + pytest 镜像 tests**，与 REFACTOR_DESIGN §3 完全一致，本文补齐其资产层与执行门禁。总工期约 5 个工作日，每一步以"214 测试保持绿"为提交门禁。

---

## 2. 现状全景盘点（实测）

### 2.1 代码规模与分布

| 区域 | 文件数 | 行数 | 说明 |
|---|---|---|---|
| 根目录 `.py` | **34** | **14,613** | 库/入口/脚本混杂（明细见 §3） |
| `tools/`（vendored） | 4 | 1,644 | OffSeeker vendor 层，`__init__` 表面干净 |
| `tests/` | 8（7 测试 + conftest） | 2,496 | 214 用例，16.7s 全绿 |
| 根目录顶层 **总计** | 42 | 18,753 | — |

**体量头部集中**：`search_harness_pipeline_v4.py` 一个文件 3,153 行（占根目录代码 21.6%），`search_agent_v3.py` 1,524 行（10.4%），前 5 大文件合计 6,789 行（46.5%）。

### 2.2 git 状态（实测，2026-08-20）

| 项 | 实测值 | 与 REFACTOR_DESIGN 基线的偏差 |
|---|---|---|
| 仓库根 | `/Users/soovv/search_data_systhesis`（**SearchHarness_0425 是子目录**，非独立仓库） | 文中未点明 |
| 当前分支 | `test`（HEAD `83e0a07`） | ⚠️ 文中基线为 `master a67a50b`——**执行前必须裁定基点** |
| git tag | **无任何 tag** | ⚠️ `pre-refactor-baseline` 尚未打 |
| 未提交修改 | 6 个文件：`answer_verifier.py / planning_agent_v3.py / search_agent_v3.py / tests/conftest.py / tests/test_source_accuracy.py / verify_source_accuracy.py` | ⚠️ 工作区非净 |
| 未跟踪文件 | **`tools/`（整个 vendor 层！）**、`tests/__init__.py`、`docs/REFACTOR_DESIGN.md` | ⚠️ `git mv` 对未跟踪文件**无历史可保**，必须先提交 |
| 历史跟踪的产物 | `results/seed123_full10_p1e.json`、`results/seed123_full10_p1e_v2.json`、`results/seed123_pos5_p1e.json` | 与 `.gitignore` 的 `results/` 规则冲突（ignore 前已入库） |

### 2.3 运行时与其他资产

| 资产 | 实测 | 状态 |
|---|---|---|
| `logs/` | **955MB / 354 条目**（含 `cluster_run_seed123_k100` 等集群产物） | 已 gitignore ✅，本地磁盘压力真实存在 |
| `results/` | 1.7MB / 206 条目 | 已 gitignore，但 3 个历史文件仍被跟踪 ⚠️ |
| `docs/` | 21 文件：13 份实验分析 md + 1 份设计文档 + **1 个数据集 csv + 5 个 manifest json** | 全部被 git 跟踪；数据与文档混放 ⚠️ |
| 根目录 `failure_taxonomy_report.json` | **272KB 孤儿产物**（`failure_taxonomy.py` 的输出），未跟踪、无 gitignore 覆盖 | ⚠️ 无归属 |
| `__pycache__/`（根目录，588 项） | 裸名导入运行的副产物 | 已 gitignore；包化后应消失 |
| `.DS_Store` | 存在 | 已 gitignore ✅ |
| `.env*` | **不存在** | 依赖操作者本地配置，README §构建环境 已说明 |

### 2.4 被 README 文档漂移掩盖的事实

- README「目录结构」节只列了 `tests/` 下 2 个文件（37+35 例）——**实际 7 个测试文件、214 例**；
- README 提到 `WORKLOG.md`——**该文件已不存在**（REFACTOR_DESIGN step6 要求"WORKLOG 记录改造完成"，需在改造时补建或修正 README）；
- README 的目录结构节完全未提 `analyze_failed_subtasks.py / diagnose_trajectories.py / failure_taxonomy.py / build_results_from_trajectories.py / run_single_verify.py / answer_verifier.py / model_profiles.*`。

---

## 3. 按关注点的文件归类

> 本表是对**所有**根目录条目的事实归类（不含工具/测试，它们已成型），是 §7 映射表的分类基础。标 🆔 的文件一起构成不可拆的迁移单元。

### 3.1 核心流水线（Orchestration）
| 文件 | 行数 | 职责 |
|---|---|---|
| `search_harness_pipeline_v4.py` 🆔P | 3,153 | `SearchHarnessPipelineV4`：编排主循环（`run()` :145–648）、阶段状态机、候选池、验证队列、子任务并发、反馈 hooks、轨迹写入、收尾策略——**god-object**（REFACTOR_DESIGN §5 已逐方法映射） |

### 3.2 Agents（5）
| 文件 | 行数 | 职责 |
|---|---|---|
| `planning_agent_v3.py` | 669 | 规划 Agent（`__file__` 相对加载 prompt md :52,:89） |
| `search_agent_v3.py` | 1,524 | 执行 Agent；**私有引用** `query_critic._normalize_query` :27 |
| `search_crawl_controller.py` | 528 | 搜索/抓取预算控制器 |
| `search_finalizer.py` | 667 | 定稿 Agent |
| `answer_verifier.py` | 571 | 答案验证器（被 finalizer 依赖） |

### 3.3 Critics（3）
| 文件 | 行数 | 职责 |
|---|---|---|
| `query_critic.py` | 716 | 查询评审（`QueryCritic / QueryVerdict / SUGGEST_PIVOT / _normalize_query`） |
| `subtask_critic.py` | 477 | 子任务评审 |
| `planning_direction_critic.py` | 248 | 方向评审 |

### 3.4 状态 / 记忆（2，干净的叶子 ✅）
| 文件 | 行数 | 职责 |
|---|---|---|
| `search_memory.py` | 769 | 候选状态存储（仅依赖 stdlib + loguru） |
| `query_history.py` | 308 | 查询历史记忆 |

### 3.5 LLM 基础设施（5 py + 1 yaml）
| 文件 | 行数 | 职责 / 被消费面 |
|---|---|---|
| `openai_client_factory.py` | 42 | `build_openai_client` —— **被 12 个文件直接 import**（9 业务 + `llm_client` 内部 + 2 脚本） |
| `llm_client.py` | 118 | 客户端缓存 + 重试（`get_llm_client`） |
| `llm_reasoning_compat.py` | 691 | 推理模型流式兼容（reasoning_content / 思考预算），被 9 处 import |
| `llm_error_utils.py` | 73 | 错误分类 |
| `model_profiles.py` + `model_profiles.yaml` | 207 + 71 | 模型 profile（yaml 同目录加载 :35） |

### 3.6 配置（1）
| 文件 | 行数 | 职责 |
|---|---|---|
| `config.py` | 160 | `settings()` 惰性构造不可变 `Settings`（已是前人收敛成果 ✅，但收敛未完：pipeline `__init__` 仍直读 8+ 个 env，见 REFACTOR_DESIGN Q5） |

### 3.7 轨迹记录（2 → 需合并）
| 文件 | 行数 | 实况 |
|---|---|---|
| `trajectory_recorder.py` | 248 | 旧版 12 方法，**无 `record_event`**；pipeline 仅剩 :3145 demo 块与 :69 类型注解在用它——**运行时已名存实亡** |
| `trajectory_recorder_enhanced.py` | 805 | 实际运行时实现（`record_event` ×12 处自用；pipeline 回调 21 处依赖它）；由 `run_browsecomp.run_single_task` / `run_single_verify.py:88` 注入 pipeline |

### 3.8 评测服务 + CLI 入口（1，二合一）
| 文件 | 行数 | 内部结构（实测行号） |
|---|---|---|
| `run_browsecomp.py` | 522 | 解密 `_derive_key/_decrypt` :41/:48 · 模型解析 :74/:83 · `LLMGrader` :109 · 答案抽取 :173 · 单任务 :215 · 批量评测 :308 · `main()` :465。**被 4 个脚本当库 import**，私有 `_decrypt` 被跨文件引用 |

### 3.9 运行入口脚本（3）
`run_browsecomp_fixed_sample.py`（328，数据集路径硬编码 `_HERE/"docs"/"browse_comp_test_set.csv"` :29）、`run_seed_repeats.py`（178，subprocess 包装）、`run_single_verify.py`（117）。

### 3.10 冒烟 / 调试脚本（4）
`smoke_test_simple.py`（103，端到端单问题）、`smoke_test_thinking.py`（160，思考模式对比）、`debug_llm_smoke.py`（231，纯端点连通性，**零项目内依赖**）、`debug_serper_smoke.py`（43，纯 Serper 连通性，**零项目内依赖**）。
> 注：后两个本质是**运维探针**（probe），与"跑通 pipeline 的冒烟"不是一类，命名却都叫 smoke/debug——归类时应区分（见 §7）。

### 3.11 分析 / 后处理脚本（7）
`regrade_results.py`（199）、`build_results_from_trajectories.py`（198）、`build_seed123_k10_full.py`（59）、`analyze_failed_subtasks.py`（102）、`diagnose_trajectories.py`（122，**硬编码** `logs/trajectories_rerun6_full/GLM-5.2` 默认值 :113）、`failure_taxonomy.py`（199）、`verify_source_accuracy.py`（78，直取 `tools.search_tools` 私有函数 :33）。

### 3.12 非代码资产（根目录 + docs/）
| 资产 | 数量 | 归类 |
|---|---|---|
| prompt md（`planning_agent_prompt_{v3,simple}.md`、`search_agent_prompt_{v3,simple}.md`） | 4 | 包资源（随 agent 代码走） |
| `model_profiles.yaml` | 1 | 包资源（随 `model_profiles.py` 走，同目录加载天然兼容） |
| `docs/browse_comp_test_set.csv` | 1 | **数据**，非文档 |
| `docs/seed123_{k1,k2,k3,k10,k100}_manifest.json` + `seed123_k10_full.json` | 6 | **数据**（固定子集 + manifest），非文档 |
| `docs/` 实验分析 md（`budget_test_*` / `cluster_run_*` / `experiment_compare_*` / `insight_*` / `kimi_k3_*` / `latency_*` / `real_test_*` / `refactor_test_*` / `smoke_test_*` ×3 / `strengthening_*`） | 13 | 一次性**实验报告**，应归档子目录 |
| `docs/REFACTOR_DESIGN.md` + 本文 | 2 | 长期设计文档 |
| 根目录 `failure_taxonomy_report.json`（272KB） | 1 | 分析产物，应下沉 `results/` |
| `results/seed123_*.json` ×3（已跟踪） | 3 | 评测产物，应退出 git 跟踪 |

---

## 4. 结构问题诊断

### 4.1 代码层问题（Q1–Q9 已由 REFACTOR_DESIGN §1.1 详录，本文只列索引 + 实测增量）

| # | 问题（引用 REFACTOR_DESIGN） | 本文实测增量 |
|---|---|---|
| Q1 | 裸名导入 + sys.path hack | **实测 12 处 `sys.path` 操作**（8 个库文件 + 4 处测试/脚本），且 `search_harness_pipeline_v4.py:31`、`run_browsecomp.py:33`、`search_agent_v3.py:25` 等把**父目录**而非项目目录插入路径——副作用半径比文档所述更大；`answer_verifier.py:43-46` 的写法（`if root_path in sys.path: pass else: insert`）说明该 hack 是多人多时期各自打补丁的沉积 |
| Q2 | god-object 3153 行 | 无增量（§1.1 已准确） |
| Q3 | 入口与库混用 | 实测被库式 import 的脚本为 4 个 + 1 个 subprocess 包装，与文档一致 |
| Q4 | 双 recorder 分叉 | 实测pipeline 运行期 21 处只调 enhanced 的 `record_event`；旧版仅剩 demo 块（:3145）与签名注解（:69）——**删除旧版无运行时风险**，REFACTOR_DESIGN 的合并方案安全 |
| Q5 | 配置三轨并存 | 无增量 |
| Q6 | 私有 API 跨文件引用 | 无增量 |
| Q7 | conftest 点对点 patch | **增量发现**：`LLM_CLIENT_CONSUMERS` 清单（8 项）**未包含 `search_harness_pipeline_v4`**——pipeline 自身也 import 了 `build_openai_client`（:27）。当前测试绿是因为 pipeline 构造的全部组件经 agents 层间接被 patch；一旦 pipeline 恢复运行期自建 LLM 客户端的分支被触发，就会打真网络。这是 **P0 级测试安全缺口** |
| Q8 | 资源文件平铺 | 无增量（4 prompt md + yaml + csv/json 路径依赖已核实） |
| Q9 | vendor 私有函数被直取 | 无增量（`verify_source_accuracy.py:33`） |

### 4.2 资产与运维层问题（本文新增，A 系列）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| A1 | **数据文件混入 docs/** | `docs/browse_comp_test_set.csv`、`docs/seed123_*.json` ×6，且 `run_browsecomp_fixed_sample.py:29` 硬编码引用 | docs 不再是纯文档；数据文件无版本语义、无不可变性约定 |
| A2 | **一次性实验报告与长期文档平铺** | docs/ 下 13 份 `*_analysis.md` / `smoke_test_*` 报告与 `REFACTOR_DESIGN.md` 同级 | 后来者无法分辨"哪些是规范、哪些是历史快照" |
| A3 | **孤儿产物** | 根目录 `failure_taxonomy_report.json` 272KB，未被 git 跟踪也无 gitignore 覆盖；README 宣称的 `WORKLOG.md` 不存在 | 新人 clone 后目录与 README 对不上 |
| A4 | **已入库的产物与 gitignore 冲突** | `results/seed123_{full10_p1e,full10_p1e_v2,pos5_p1e}.json` 仍被 git 跟踪 | ignore 规则形同虚设；后续 `git status` 噪音 |
| A5 | **logs/ 无生命周期管理** | 955MB / 354 目录，含集群运行产物 | 本地磁盘压力；`diagnose_trajectories.py:113` 等脚本把具体历史目录名硬编码为默认值，形成"活文档依赖死数据" |
| A6 | **README 文档漂移** | tests 数量、WORKLOG.md、目录清单三处过时（§2.4） | 文档失去基准作用 |
| A7 | **git 卫生阻碍重构启动** | `tools/` + `tests/__init__.py` 未跟踪；6 文件未提交修改；无 tag；分支基点未定（test vs master） | REFACTOR_DESIGN 的"git mv 保历史"与"每步 revert"策略**在未提交状态下直接失效**——这是当前最紧迫的执行阻塞 |

### 4.3 版本演化管理问题

- 文件名当版本号：`_v3`（×2）、`_v4`（×1）、`_enhanced`（×1）、`_compat`（×1）后缀说明历次演进都靠"新起文件 + 并存"完成；
- 父目录 `SearchHarness_Training/`、同级的 `MODELS_AND_TRAINING.md / EigentSearch_extracted.txt` 显示本工作区本身是 `SearchHarness_0413_v3` 的演化结果——**目录名也在当版本号**；
- 无任何 git tag 锚定历史形态，回找"v3 行为"只能靠 commit 考古。

---

## 5. 业界成熟方案对标

> `REFACTOR_DESIGN.md` §2 已对 lm-evaluation-harness / HELM / OpenAI evals / OpenHands / SWE-bench 做过框架级对照并提炼出 5 条公理。本节按另一组社区基准补充，每条给出**核心思想 + 本项目的具体落点**，不做生搬硬套。

### 5.1 PyPA 打包指南：src layout vs flat layout（packaging.python.org）

- **核心思想**：`src/<package>/` 布局让"源码目录"与"可导入路径"隔离——测试与脚本**只能** import 安装后的包，杜绝"从项目根碰巧能 import 成功、安装后却坏"的假象；flat layout 适合单模块小项目。
- **对本项目的适用点**：本项目 34 个裸名模块正是 flat layout 失控形态——CWD 即 import 路径，靠 `sys.path.insert` 维生（Q1）。迁移到 `src/search_harness/` 后，14,613 行代码的导入只可能来自 editable install 或 pytest 的 `pythonpath=["src"]`，从机制上消灭整个 Q1 问题族。
- **务实妥协**（与 REFACTOR_DESIGN step1 一致）：不强求第一天就 `pip install -e .`——`pyproject.toml` 里 `[tool.pytest.ini_options] pythonpath=["src"]` 即可让 pytest 绿；`pip install -e .` 作为 cli 入口（console script）落地时的顺带产物。

### 5.2 Cookiecutter Data Science（drivendata）

- **核心思想**：研究/实验型项目按 `data/{raw,interim,processed}` · `models/`（产物）· `reports/`（报告）· `notebooks/` 分层；**数据不可变**（raw 只读）；**代码与数据物理分离**；产出不入库。
- **对本项目的适用点**：本项目是典型"评测研究 + 工程库"混合体，其 `docs/` 同时充当数据目录（A1）、`results/` 与 `reports` 混同（A4）。落点：
  - 数据文件迁出 docs 入 `data/`（csv + 6 个 json），并在 `data/README.md` 注明**不可变 + 来源 + 生成方式**（csv 是 BrowseComp 官方缓存；`seed123_k10_full.json` 由 `build_seed123_k10_full.py` 从 logs 重建）；
  - `logs/` / `results/` 明确为**产物区**（models/ 的对应物），gitignore + 定期归档，退出 git 跟踪（A4）；
  - 实验报告迁 `docs/experiments/`（reports/ 的对应物），顶层 docs 只留长期文档（A2）。
- **不照搬**：`data/{raw,interim,processed}` 三层对单一数据集过重，拍平为单层 `data/`。

### 5.3 OpenAI simple-evals / evals：runner 与 eval 逻辑分离

- **核心思想**（simple-evals）：`<task>_eval.py` 只管"数据集 → 逐题调 solver → 评分 → 汇总"，`runner.py` 只是枚举入口；BrowseComp 数据集下载即缓存、与代码分离。（openai-evals 进一步引入 yaml registry——**对本项目过重，明确不引入**，理由同 REFACTOR_DESIGN 对装饰器注册表的 YAGNI 判断。）
- **对本项目的适用点**：`run_browsecomp.py` 应当 exactly 对应 simple-evals 的角色——但现状它同时是"库（LLMGrader/decrypt/run_evaluation）+ CLI（main）+ 被 4 脚本 import 的公共设施"（Q3）。落点即 REFACTOR_DESIGN 的一分为四：`eval/`（服务层）+ `cli/`（薄壳 argparse）；改造后 `run_single_verify.py` 等脚本经 `search_harness.eval` 公开表面取 `LLMGrader/decrypt`，私有 `_decrypt` 提为公开 `decrypt`。

### 5.4 LangChain 系 agent 框架的包分层

- **核心思想**：`agents / tools / chains / llms / memory` 概念分层，Agent 实现与编排链分离，LLM 客户端抽象独立成层。
- **对本项目的适用点**：概念映射恰好一一对应本项目的 `agents/ tools/ pipeline/ llm/ memory/`——**命名可直接对齐社区惯例**，降低新人认知成本（`searcher/planner/finalizer` 进 `agents/`，编排唯一入口在 `pipeline/`）。
- **不照搬**：LangChain 是通用库、子包极深；本项目是专用应用，11 个子包一层打平即可，禁止再向下嵌套第二层概念包。Agent 保持"构造注入依赖、运行无跨 agent import"（REFACTOR_DESIGN 规则 R4 固化现状）。

### 5.5 12-Factor 配置管理 + pydantic-settings / dynaconf 实践

- **核心思想**：配置存环境变量、与代码严格分离、单一口径读取；成熟的 Python 落地是 `pydantic-settings`（类型化 BaseSettings）或 `dynaconf`。
- **对本项目的适用点**：`config.py` 已经走在这条路上（dataclass + 惰性 `settings()`），**方向正确、收口未完**——pipeline `__init__` 仍直读 8+ 个 env（Q5）。落点：
  - **现在不换 pydantic-settings**（YAGNI + 保持安装面不变，与 REFACTOR_DESIGN §6 决策一致）；
  - 分阶段把散点 `os.getenv` 全部搬进 `Settings` 字段（pipeline 的 `PLANNER_TEMPERATURE / VERIFY_RANK_ENABLED / REFLEXION_ENABLED` 等 8+ 项优先），消费方只经 `settings()` 读——这是"配置单轨化"，不依赖任何新库；
  - P3 若轨迹外发训练需要更强 schema，再独立评估 pydantic 引入。

### 5.6 pytest 官方布局约定：测试 vs 冒烟/调试脚本

- **核心思想**：`tests/` 与源码平级、（src layout 下）镜像包结构；`conftest.py` 提供共享 fixture；**可重复、无外部依赖、快速**才进 pytest——依赖真实网络/API key 的连通性探针不是测试，是脚本。
- **对本项目的适用点**：
  - `tests/` 现有 214 例全部离线可跑（FakeOpenAIClient + stub tools），性质健康 ✅；
  - `smoke_test_*` / `debug_*_smoke` 四个需要真实 API key 的脚本应归 `scripts/smoke/`——并且按 §3.10 的观察，`debug_llm_smoke / debug_serper_smoke` 是**零依赖运维探针**，命名统一为 `scripts/smoke/probe_*.py` 或并入 README「运行前检查清单」的配套命令（P3 定名，迁移时不改名先归位）；
  - conftest 的 `sys.path` hack 由 `pythonpath=["src"]` 取代、patch 点收敛为 `llm.client` 单点（Q7 + 本文 §4.1 增量：补 `search_harness.pipeline.orchestrator` 进 patch 面或确认其永不直接建客户端）。

### 5.7 语义化版本演进：后缀名 → 包内模块 + git tag

- **核心思想**：版本是**发布的快照标签**（SemVer + VCS tag），不是文件名的一部分；API 兼容演进靠包内模块组织，破坏性演进靠 major 版本与 migration note。
- **对本项目的适用点**：
  - 迁移后**模块名一律去版本后缀**：`planning_agent_v3 → agents/planner.py`、`search_agent_v3 → agents/searcher.py`、`search_harness_pipeline_v4 → pipeline/orchestrator.py`；
  - 类名 `SearchHarnessPipelineV4` 短期保留（外部脚本/训练管线若有引用，用 `pipeline/__init__.py` 的 re-export 原样导出），待 P3 再评估改为 `SearchHarnessPipeline` + 别名过渡；
  - 历史形态用 **git tag 锚定**（先借改造契机打 `pre-refactor-baseline`；后续按 `v4.x` 语义打功能 tag）；`_enhanced/_compat` 类分叉一律合并为默认实现（双 recorder 合并即首例）。

---

## 6. 目标结构

采纳 `REFACTOR_DESIGN.md` §3.1 的目录树（**逐字有效，不再重复**），本文补充 REFACTOR_DESIGN 未覆盖的资产层细节，并标注三处修正：

```
SearchHarness_0425/
├── pyproject.toml                  # 新增：包定义 + pytest pythonpath + console script
├── README.md                       # step6 更新（瘦身：实测记录迁 docs/experiments/）
├── requirements.txt                # 保留（P3 再议并入 pyproject）
├── .gitignore / .env.example       # 补充产物条目 / 新增（12-Factor 配置样例，P2）
│
├── src/search_harness/             # 【同 REFACTOR_DESIGN §3.1，不重复】
│   ├── config/ contract/ llm/ memory/ tools/ agents/ trajectory/ pipeline/ eval/ cli/
│
├── scripts/
│   ├── run/        run_browsecomp.py(兼容壳) · run_browsecomp_fixed_sample.py · run_seed_repeats.py · run_single_verify.py
│   ├── smoke/      smoke_test_simple.py · smoke_test_thinking.py · debug_llm_smoke.py · debug_serper_smoke.py
│   └── analysis/   regrade_results.py · build_results_from_trajectories.py · build_seed123_k10_full.py
│                    · analyze_failed_subtasks.py · diagnose_trajectories.py · failure_taxonomy.py · verify_source_accuracy.py
│
├── data/                            # ★ 新增 README.md 注明来源与不可变性（§5.2）
│   ├── README.md
│   ├── browse_comp_test_set.csv     # ← docs/（官方缓存，raw）
│   ├── seed123_k10_full.json        # ← docs/（build_seed123_k10_full.py 的产物，processed）
│   └── seed123_*_manifest.json ×6   # ← docs/
│
├── tests/                           # 镜像包结构（P2 起逐步按 llm/ agents/ pipeline/ 分子目录，可选）
│
├── docs/
│   ├── REFACTOR_DESIGN.md / PROJECT_STRUCTURE_PLAN.md / ARCHITECTURE.md(step6 新增)
│   └── experiments/                 # ★ 归档 13 份一次性实验/冒烟报告（git mv 保历史）
│
├── artifacts/                       # ★ 新增（可选，P3）：归档需要长期保留的历史 results 快照
├── results/  logs/                  # 产物区（gitignore，不变）；logs/ 加归档约定（§5.2）
└── （third_party/ 修正：REFACTOR_DESIGN §3.1 树中列出但实际已不存在，删除该条目）
```

**对 REFACTOR_DESIGN §3.1 的三处修正**：
1. `third_party/` 条目删除——工作区已无此目录（tools/ 自 OffSeeker vendor 后即独立；父目录的 `OffSeeker-main/` 仅作参考源码，不进本目录树）；
2. 增补 `data/README.md` 与 `docs/experiments/`、`artifacts/`（资产层，§5.2）；
3. 增补 `.env.example`（12-Factor 落地：README §配置说明 的环境变量清单物化为样例文件，P2）。

---

## 7. 全量文件映射表

> 根目录 **34 个 `.py` + 全部非 py 条目逐一归属**。方式列：**移动**=git mv 保历史；**拆分**=手工；**合并**=两源合一；**归档**=移出工作区主视野；**删除**=可安全移除。代码文件的目标位置与 `REFACTOR_DESIGN.md` 附录 A 完全一致（重复列出是为"一张表覆盖全部"的执行便利）。

### 7.1 库代码（17 + 2 + 1 拆分）

| # | 现文件 | 行数 | 去向 | 方式 | 改动要点 |
|---|---|---|---|---|---|
| 1 | `search_harness_pipeline_v4.py` | 3153 | `pipeline/orchestrator.py` → step4b 再抽 8 模块 | 移动+拆分 | REFACTOR_DESIGN §5（两子步：先物理搬迁后职责抽取） |
| 2 | `planning_agent_v3.py` | 669 | `agents/planner.py` | 移动 | prompt 路径 2 处（:52,:89）改 `prompts/` |
| 3 | `search_agent_v3.py` | 1524 | `agents/searcher.py` | 移动 | `_normalize_query` 改公开名（:27）；prompt 路径 2 处 |
| 4 | `search_crawl_controller.py` | 528 | `agents/crawl_controller.py` | 移动 | 删 sys.path hack |
| 5 | `search_finalizer.py` | 667 | `agents/finalizer.py` | 移动 | 同上 |
| 6 | `answer_verifier.py` | 571 | `agents/verifier.py` | 移动 | 同上 |
| 7 | `query_critic.py` | 716 | `agents/critics/query.py` | 移动 | `_normalize_query` → 公开 `normalize_query` + 旧别名 |
| 8 | `subtask_critic.py` | 477 | `agents/critics/subtask.py` | 移动 | 删 sys.path hack |
| 9 | `planning_direction_critic.py` | 248 | `agents/critics/direction.py` | 移动 | 同上 |
| 10 | `search_memory.py` | 769 | `memory/search_state.py` | 移动 | 零改动（叶子） |
| 11 | `query_history.py` | 308 | `memory/query_history.py` | 移动 | 零改动（叶子） |
| 12 | `config.py` | 160 | `config/settings.py` | 移动 | 零改动 |
| 13 | `openai_client_factory.py` | 42 | `llm/factory.py` | 移动 | 零改动（叶子） |
| 14 | `llm_client.py` | 118 | `llm/client.py` | 移动 | 成为唯一 patch 点（Q7 收敛） |
| 15 | `llm_reasoning_compat.py` | 691 | `llm/compat.py` | 移动 | 零改动 |
| 16 | `llm_error_utils.py` | 73 | `llm/errors.py` | 移动 | 零改动（叶子） |
| 17 | `model_profiles.py` | 207 | `llm/profiles.py` | 移动 | 零改动 |
| 18 | `model_profiles.yaml` | 71 | `llm/profiles.yaml` | 移动 | 同目录搬迁，加载路径天然正确 |
| 19 | `trajectory_recorder.py` | 248 | **合并删除** | 删除新版吸收 | 旧版仅剩 demo 块与注解用途；annotated 引用改指新类 |
| 20 | `trajectory_recorder_enhanced.py` | 805 | `trajectory/recorder.py` | 移动+承接合并 | 类名定 `TrajectoryRecorder`；`__init__` 留 `TrajectoryRecorderEnhanced` 别名一阶段 |
| 21 | `run_browsecomp.py` | 522 | 一分为四：`eval/decrypt.py` + `eval/grader.py` + `eval/browsecomp.py` + `cli/browsecomp.py`；另留 `scripts/run/run_browsecomp.py` 兼容壳 | 拆分 | `_decrypt` 提公开名 `decrypt`；4 个库式消费脚本改 import |

### 7.2 脚本（14）

| # | 现文件 | 去向 | 方式 | 改动要点 |
|---|---|---|---|---|
| 22 | `run_browsecomp_fixed_sample.py` | `scripts/run/` | 移动 | csv 路径 `docs/` → `data/`；import 改包路径 |
| 23 | `run_seed_repeats.py` | `scripts/run/` | 移动 | subprocess 命令指向兼容壳（保持 muscle memory） |
| 24 | `run_single_verify.py` | `scripts/run/` | 移动 | recorder import 改包路径 |
| 25 | `smoke_test_simple.py` | `scripts/smoke/` | 移动 | import 改包路径 |
| 26 | `smoke_test_thinking.py` | `scripts/smoke/` | 移动 | 同上 |
| 27 | `debug_llm_smoke.py` | `scripts/smoke/` | 移动 | 零项目依赖，仅挪位（P3 再议改名 `probe_*`） |
| 28 | `debug_serper_smoke.py` | `scripts/smoke/` | 移动 | 同上 |
| 29 | `regrade_results.py` | `scripts/analysis/` | 移动 | `sys.path` hack 删除；import 改包路径 |
| 30 | `build_results_from_trajectories.py` | `scripts/analysis/` | 移动 | 同上 |
| 31 | `build_seed123_k10_full.py` | `scripts/analysis/` | 移动 | 同上 |
| 32 | `analyze_failed_subtasks.py` | `scripts/analysis/` | 移动 | 硬编码 results 路径参数化（P3，迁移期不动） |
| 33 | `diagnose_trajectories.py` | `scripts/analysis/` | 移动 | 硬编码 logs 子目录默认值保留（A5 风险登记，P3 参数化） |
| 34 | `failure_taxonomy.py` | `scripts/analysis/` | 移动 | import 改包路径 |
| 35* | `verify_source_accuracy.py` | `scripts/analysis/` | 移动 | **改经 `tools/__init__` 公开表面**（Q9 收口，REFACTOR_DESIGN step5） |

（编号 22–35 共 14 个脚本，与 §3.9–§3.11 的分类计数一致：运行入口 3 + 冒烟/调试 4 + 分析/后处理 7。）

### 7.3 非代码资产

| # | 现路径 | 去向 | 方式 |
|---|---|---|---|
| 36 | `planning_agent_prompt_v3.md` | `agents/prompts/planner_v3.md` | 移动（引用方 2 行改动） |
| 37 | `planning_agent_prompt_simple.md` | `agents/prompts/planner_simple.md` | 移动 |
| 38 | `search_agent_prompt_v3.md` | `agents/prompts/searcher_v3.md` | 移动 |
| 39 | `search_agent_prompt_simple.md` | `agents/prompts/searcher_simple.md` | 移动 |
| 40 | `docs/browse_comp_test_set.csv` | `data/browse_comp_test_set.csv` | 移动（`run_browsecomp*.py` 路径常量 1 处改动） |
| 41 | `docs/seed123_k10_full.json` | `data/seed123_k10_full.json` | 移动 |
| 42 | `docs/seed123_{k1,k2,k3,k10,k100}_manifest.json` | `data/` | 移动 ×5 |
| 43 | `docs/` 下 13 份实验分析 md | `docs/experiments/` | 归档（git mv 保历史；README 内若有链接同步更新） |
| 44 | 根目录 `failure_taxonomy_report.json`（272KB，未跟踪） | `results/`（已是产物目录且 gitignore） | 归档（本地移动，无 git 操作） |
| 45 | `results/seed123_{full10_p1e,full10_p1e_v2,pos5_p1e}.json`（已跟踪） | 仍在 `results/`，但 `git rm --cached` 退出跟踪 | 去跟踪（保留本地文件） |
| 46 | `README.md` | 根目录保留 | 更新（step6；实验实录迁 experiments） |
| 47 | `requirements.txt` | 根目录保留 | 不变（P3 评估并入 pyproject） |
| 48 | `.gitignore` | 根目录保留 | 增补：`failure_taxonomy_report*.json`、`artifacts/` |
| 49 | `__pycache__/`、`.pytest_cache/`、`.DS_Store` | 不适用 | 删除本地残留（已 gitignore；包化后根目录 `__pycache__` 会自然消失） |
| 50 | `tests/`（8 文件） | 原位，逐步镜像包结构 | 仅改 import（P2 再分子目录，`tests/__init__.py` 现状提交保留） |
| 51 | `logs/`（955MB） | 原位 | 加归档约定；**不参与 git**；集群产物（`cluster_*`）可另行冷归档 |

---

## 8. 分阶段迁移计划

> **阶段编号与 `REFACTOR_DESIGN.md` §8 的 step0–step6 一一对应**（本文不另起编号体系）；本文按 P0/P1/P2 优先级视角重组并补充执行门禁。每步独立 commit；门禁失败 → 单步 revert，不夹带前进；总回滚兜底：`git reset --hard pre-refactor-baseline`。

### P0 —— 启动准备（REFACTOR_DESIGN step0 + 本文 git 卫生增补，0.5 个工作日）

**目标：让"git mv 保历史 + 逐步 revert"成为可能——这是后续一切的前提。**

| 序 | 动作 | 验证检查点 |
|---|---|---|
| P0-1 | **裁定分支基点**：确认在 `test` 分支（HEAD `83e0a07`）执行还是合并回 `master`（`a67a50b`）后执行——REFACTOR_DESIGN 的基线描述与实际分支不一致，须先收敛 | `git branch --show-current` 输出与计划记录一致 |
| P0-2 | **先提交 `tools/` 与 `tests/__init__.py`**（当前未跟踪！）为独立 commit `chore: vendor tools/ layer as-is` | `git status` 无 `?? tools/`；`git log --oneline -1 -- tools/` 有记录 |
| P0-3 | 处理 6 个未提交修改文件：逐个评审 → 提交（推荐）或 `git stash list` 清单化 | `git status --short` 干净 |
| P0-4 | 孤儿产物归档：`mv failure_taxonomy_report.json results/`；`.gitignore` 增补产物通配 | 根目录无孤儿 json |
| P0-5 | 去跟踪历史产物：`git rm --cached results/seed123_{full10_p1e,full10_p1e_v2,pos5_p1e}.json`（本地文件保留） | `git ls-files results/` 为空且本地文件仍在 |
| P0-6 | 打基线 tag：`git tag pre-refactor-baseline`；建执行分支 `refactor/modularization`；记录基线 `pytest tests/ -q \| tee logs/baseline_pytest_214.txt`；清根 `__pycache__` | tag 存在；基线文件 214 passed |

**P0 出口门禁**：`git status` 干净 + tag 存在 + **pytest 214 passed**。

### P1 —— 包化落地（REFACTOR_DESIGN step1 + step2，1 个工作日）

**目标：`pip install -e .` 可用 / pytest 无 sys.path 依赖；LLM 层单点可补丁。**

| 序 | 动作（细节见 REFACTOR_DESIGN step1/step2） | 验证检查点 |
|---|---|---|
| P1-1 | 新建 `pyproject.toml`（setuptools src layout + `pytest.pythonpath=["src"]` + `sh-browsecomp` console script）；建空骨架包 | `pip install -e .` 成功；`python -c "import search_harness"` 通过 |
| P1-2 | step1：`config.py → config/settings.py`；`run_browsecomp.py` 一分为四 | 4 个库式消费脚本 import 全改后 `pytest 214 passed` + `python -m search_harness.cli.browsecomp --help` 正常 |
| P1-3 | step2：llm 五文件 + yaml 入 `llm/`；9 个业务消费文件机械替换 import；conftest patch 收敛单点 | `pytest 214 passed`；裸名残留扫描（附录 B）零命中 |
| P1-4 | **（本文新增）修复 conftest 覆盖缺口**：确认 `search_harness.pipeline.orchestrator` 的 `build_openai_client` 引用点也被 patch（或消费统一改走 `get_llm_client` 后自然覆盖） | 审查 + 一次"拔掉真实 key 跑全量测试"演练（无网络告警） |

**P1 出口门禁**：`pytest 214 passed` + cli `--help` 可运行 + `grep -rn "sys.path" src/ scripts/` 仅剩待迁移脚本。

### P2 —— 领域层迁移与 god-object 拆分（REFACTOR_DESIGN step3 + step4，2.5–3 个工作日）

**目标：全部业务代码入包；pipeline god-object 消除；行为不变。**

| 序 | 动作 | 验证检查点 |
|---|---|---|
| P2-1 | step3：memory / agents（含 prompts）/ trajectory 合并迁移；`tools/` 入包 | `pytest 214 passed`；`TrajectoryRecorderEnhanced` 别名可用 |
| P2-2 | step4a：pipeline 整文件 `git mv` 入 `pipeline/orchestrator.py` | `pytest 214 passed`（纯搬迁） |
| P2-3 | step4b：按 REFACTOR_DESIGN §5.2 顺序（tracing→finish→feedback→stages→candidates→verification→subtasks）逐模块抽取，**每模块一次 commit** | 每次抽取后 `pytest 214 passed`；`tests/test_concurrency.py` 单独绿（私有名可达性）；全部完成后 orchestrator.py ≤ ~700 行 |
| P2-4 | 真机冒烟：单题 `sh-browsecomp --positions 5 ...`（需真实 key，人工触发） | 轨迹文件生成 + verdict 与基线同分布（不强求同答，关注不崩与结构键完整） |

**P2 出口门禁**：`pytest 214 passed` + `test_concurrency / test_pipeline` 全绿 + 真机冒烟通过。

### P3 —— 资产与文档收口（REFACTOR_DESIGN step5 + step6 扩展，1 个工作日）

**目标：目录树与 §6 完全一致；文档/数据/产物分区明确。**

| 序 | 动作 | 验证检查点 |
|---|---|---|
| P3-1 | step5：14 脚本归位 `scripts/{run,smoke,analysis}`；数据文件入 `data/` + `data/README.md`；`docs/` 实验报告 git mv 入 `docs/experiments/` | 各脚本 `--help` 冒烟通过；csv 引用路径无残留（附录 B 扫描） |
| P3-2 | 新增 `.env.example`；`.gitignore` 增补产物条目；`verify_source_accuracy.py` 收口 tools 公开表面 | `grep` 无 `tools.search_tools import _` 私有引用 |
| P3-3 | step6：README 瘦身更新（目录结构节按 §6 重写；实验实录迁移后以链接保留）；新增 `docs/ARCHITECTURE.md`（REFACTOR_DESIGN 精简长期版）；补 `WORKLOG.md` 或修正 README 引用 | 新人视角走查：clone → install → pytest → `--help` → probe，全链路 ≤15 分钟 |
| P3-4 | （可选/靠后）logs/ 冷归档脚本 + `artifacts/` 约定；README 记录产物生命周期约定 | — |

**P3 出口门禁（改造收官）**：附录 B 全量命令集通过 + 目录树与 §6 一致 + `pytest 214 passed`。

### 里程碑视图（与 REFACTOR_DESIGN §8.0 Gantt 对齐）

```
P0(0.5d)  ──►  M0 基点+tag+基线锁定
P1(1d)    ──►  M1 可 pip install -e .  →  M2 LLM 层收敛
P2(2.5–3d)──►  M3 recorder 合并  →  M4 god-object 消除
P3(1d)    ──►  M6 全流程回归 · 收官
```

---

## 9. import 兼容与 git 历史保留策略

### 9.1 import 兼容（引用 REFACTOR_DESIGN 既定机制，强调执行纪律）

| 机制 | 用途 | 退役条件 |
|---|---|---|
| 各包 `__init__.py` re-export（清单见 REFACTOR_DESIGN §3.3） | 消费方只依赖包表面，内部文件名后续可再调整 | 永久机制（即包 API 面） |
| `search_harness/__init__.py` 惰性 `__getattr__` 导出 pipeline | 避免 `import search_harness` 拉起全依赖链 | 永久 |
| 私有符号公开化 + 旧别名（`normalize_query` / `TrajectoryRecorderEnhanced`） | Q6/Q4 过渡 | 别名留存一个阶段（至 P3 收官 +1 个迭代）后删除 |
| 类属性重绑定（REFACTOR_DESIGN §5.1） | step4b 拆分后 `test_concurrency.py` 引用的 5 个未绑定私有方法仍可达 | 测试逐步改测 helper 函数后（不强制时间表） |
| `scripts/run/run_browsecomp.py` 兼容壳 | 保留命令行肌肉记忆 + `run_seed_repeats.py` 的 subprocess 调用不变 | 一个阶段后由 README 引导到 `sh-browsecomp` |
| 包内一律**绝对导入**（`from search_harness.llm import ...`） | 重构抗扰、grep 友好 | 永久约定（写入 README/ARCHITECTURE） |

### 9.2 git 历史保留

1. **能 mv 先 mv，改名后改动分两个 commit**（REFACTOR_DESIGN R7）；`git log --follow` 对单文件 rename 可追溯，拆分型文件（run_browsecomp / pipeline）历史在 mv 那一步锚定；
2. **当前必须先补提交**（P0-2）：`tools/` 与 `tests/__init__.py` 未跟踪，此时任何 `git mv` 都无从谈起；
3. 仓库根在**父目录**（`search_data_systhesis/`），所有 `git mv` 命令在 `SearchHarness_0425/` 子目录内执行不影响历史语义（git 按内容相似度识别 rename）；
4. 每步 commit message 统一前缀 `refactor(stepN): ...`，基线 tag `pre-refactor-baseline` + 收官 tag `post-refactor-v1`（落实 §5.7 的 tag 管理起点）；
5. `docs/` 实验报告归档用 `git mv`（历史保留）；`results/` 三文件用 `git rm --cached`（内容保留在 commit 历史，工作区文件不动）。

---

## 10. 风险清单与缓解

> 代码层风险 R1–R10 见 `REFACTOR_DESIGN.md` §9，逐条有效。下表为**本文新增/加注**的资产与执行类风险；总兜底不变：`git reset --hard pre-refactor-baseline && git clean -fdx src/ scripts/ data/`。

| # | 风险 | 概率/影响 | 缓解 |
|---|---|---|---|
| S1 | **分支基点漂移**：在 `test` 分支上施工，`master` 后续合入冲突放大 | 中/高 | P0-1 先裁定；施工期间禁止业务改动并入施工分支，完成后一次性合回 |
| S2 | **tools/ 未提交即搬迁** | 若不执行 P0-2：确定/高 | P0-2 强制前置；`git mv` 前 `git log --follow` 抽查 |
| S3 | **conftest patch 缺口误打真网络**（Q7 增量：清单缺 pipeline 模块） | 中/高 | P1-4 拔 key 演练；CI 加 `--disable-socket` 类防线（可选） |
| S4 | **logs/ 相对路径漂移**：脚本从项目根运行的 CWD 约定被 scripts/ 下移打破（`diagnose_trajectories.py:113` 等默认值） | 中/中 | 迁移期脚本默认值一律保留 CWD 相对并 README 固化"从项目根运行"；P3 逐脚本参数化 |
| S5 | **`load_dotenv()` 向上查找层级变化**（scripts 下移一层） | 低/低 | python-dotenv 向上递归查找 `.env` 天然兼容；P3 手工冒烟验证 |
| S6 | **数据集路径引用遗漏**（`run_browsecomp_fixed_sample.py:29` → `data/`） | 中/中 | P3-1 后跑附录 B 残留扫描 + 一次 `--help`/加载冒烟 |
| S7 | **去版本后缀后外部引用断链**（训练管线按 `trajectory_recorder_enhanced` / `SearchHarnessPipelineV4` 名引用） | 低/高 | 别名 + re-export 过渡（§9.1）；父目录的消费脚本（`batch_generate_trajectories.py` 等）扫描确认后再删别名 |
| S8 | **中途停手的半迁移态** | 中/中 | 每步 ≤1d 且独立可停；step4a/4b 间允许长期停留（结构已合法）；P0~P3 任一出口门禁不过即驻停 |
| S9 | **README/文档与实际再次漂移** | 高/低（复发性） | P3-3 新人走查门禁；后续 PR 模板加"目录变更同步 README"勾选（可选） |

---

## 附录 A：当前基线实测数据

| 指标 | 实测值（2026-08-20） |
|---|---|
| 测试基线 | `python -m pytest tests/ -q` → **214 passed in 16.72s** |
| 根目录 .py | 34 文件 / 14,613 行 |
| 最大文件 | `search_harness_pipeline_v4.py` 3,153 行（21.6%） |
| tests | 7 测试文件 + conftest 238 行 / 2,496 行 |
| sys.path 操作 | 12 处（8 库文件 + 4 测试/脚本） |
| `build_openai_client` 直接消费方 | 12 文件（9 业务 + llm_client 内部 + 2 脚本）；conftest patch 清单 8 项（缺 pipeline） |
| `logs/` | 955MB / 354 条目（gitignore ✅） |
| `results/` | 1.7MB / 206 条目（3 个历史文件仍被跟踪 ⚠️） |
| docs/ | 13 实验 md + 1 设计文档 + 1 csv + 6 json |
| git | 分支 `test`（HEAD `83e0a07`）；无 tag；6 文件修改 + 3 项未跟踪（含 `tools/`） |

## 附录 B：统一验证命令集

```bash
cd SearchHarness_0425

# 1. 门禁（每步）
python -m pytest tests/ -q                       # 214 passed
python -m search_harness.cli.browsecomp --help    # 入口冒烟（P1 起）

# 2. 残留扫描（P1/P3 后应零命中或仅剩白名单）
grep -rn "sys.path" --include="*.py" src/ tests/ scripts/ | grep -v scripts/smoke
grep -rnE "from (search_memory|query_critic|llm_reasoning_compat|llm_client|openai_client_factory|llm_error_utils|model_profiles|config|trajectory_recorder|search_agent_v3|planning_agent_v3|run_browsecomp) import" --include="*.py" src/ scripts/ tests/
grep -rn "from tools.search_tools import _" --include="*.py" .   # vendor 私有引用（Q9）

# 3. 资产层检查（P3 后）
git ls-files results/ logs/                       # 应为空
ls docs/                                          # 应只剩设计文档 + experiments/
test -f data/browse_comp_test_set.csv && test ! -f docs/browse_comp_test_set.csv

# 4. 全流程（P3 收官，需真实 key）
python -m pytest tests/ -q
sh-browsecomp --help
python scripts/smoke/debug_llm_smoke.py           # 端点连通
python scripts/smoke/smoke_test_simple.py         # 端到端单问题
```

---

*配套文档：[REFACTOR_DESIGN.md](./REFACTOR_DESIGN.md)（代码层模块化改造设计：god-object 拆分、contract 层、LLM 层规整、逐方法映射与回归门禁）*
