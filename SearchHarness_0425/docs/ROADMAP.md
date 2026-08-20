# SearchHarness 统一问题清单与优先级路线图

> **版本**：v1.0 · 2026-08-20 · 分支 `docs/roadmap-restructure`
> **用法**：这是所有改造工作的**总入口**。三份专项文档各管一层，本文把三处的问题**合并同类项**后按统一优先级排序，落地执行以本文的里程碑为准。
>
> | 专项文档 | 管辖层 |
> |---|---|
> | [`REFACTOR_DESIGN.md`](./REFACTOR_DESIGN.md) | 代码层模块化设计（god-object 拆分、contract 层、LLM 层、逐方法映射） |
> | [`PROJECT_STRUCTURE_PLAN.md`](./PROJECT_STRUCTURE_PLAN.md) | 项目结构/资产治理/迁移编排（含全量文件映射表） |
> | [`GAP_ANALYSIS.md`](./GAP_ANALYSIS.md) | 行业对标的能力维度缺口 |
> | [`experiments/`](./experiments/) | 一次性实验报告（历史快照，13 份） |

---

## 1. 统一问题清单（合并同类项）

> 编号规则：T = 主题（theme）。**来源**列标出该问题在三份文档中的原始位置：`RD` = REFACTOR_DESIGN，`SP` = PROJECT_STRUCTURE_PLAN，`GA` = GAP_ANALYSIS。

| # | 主题 | 问题陈述（合并后） | 来源 | 级别 |
|---|---|---|---|---|
| **T1** | git 卫生与流程基线 | `tools/`（1,644 行 vendor 层）与 `tests/__init__.py` 未跟踪；6 文件未提交改动；当前在 `test` 分支而设计文档以 `master` 为基线；全仓库无 tag；无 CI 门禁；3 个 `results/*.json` 与 gitignore 冲突仍被跟踪；**conftest patch 清单缺 `search_harness_pipeline_v4` 自身**（测试可能误打真实网络） | SP §4/P0，SP 附录 | **P0** |
| **T2** | 可靠性止血：resume + 成本 | 长 run 中断全丢（无任何 checkpoint/resume）；token/美元成本零统计，并发跑批烧钱不可测 | GA G2, G3 | **P0** |
| **T3** | 可复现性 | seed 只用于抽样不进 LLM 请求；无 LLM/HTTP 响应磁盘缓存；无环境锁定（Dockerfile/lockfile）——两次"同配置"实验可能得到不同结论 | GA G4 | **P0** |
| **T4** | Benchmark 抽象与结果模式 | 硬编码 BrowseComp 单数据集、入口脚本与数据集耦合；`results/` 散装 JSON 无统一 schema/run spec（合并原 GA 的 G1 + G10） | GA G1+G10 | **P0→P1** |
| **T5** | 代码层模块化 | `search_harness_pipeline_v4.py` 3,153 行 god-object；缺 contract 层（数据结构散落）；LLM 客户端 5 文件待规整；双 trajectory recorder 分叉 557 行 | RD 主线，SP §4 | **P1** |
| **T6** | 包结构与 import 秩序 | 34 个裸名模块靠 12 处 `sys.path` hack（8 处插父目录）互相导入；无 pyproject，不可 pip 安装；`_v3/_v4/_enhanced/_compat` 版本后缀固化在文件名 | SP §4/P1 | **P1** |
| **T7** | 安全 | 代码执行裸 `Popen` 无沙箱/网络隔离；无 guardrails；无 secrets 扫描（合并原 GA 的 G5 + G12） | GA G5+G12 | **P1** |
| **T8** | 执行层扩展 | 纯 ThreadPoolExecutor、worker 数硬编码 6+ 处、无 per-provider 并发治理、无分布式（合并原 GA 的 G6 + G11） | GA G6+G11 | **P2** |
| **T9** | 评估严谨性 | 只有裸 accuracy，无置信区间/显著性；LLM judge 无人工校准基线（合并原 GA 的 G8 + G9） | GA G8+G9 | **P1** |
| **T10** | 结构化观测 | 无 span 级 tracing；延迟分析靠事后人工报告，单任务时间线不可视 | GA G7 | **P1** |
| **T11** | 资产治理 | `logs/` 955MB/354 目录无生命周期策略；根目录 272KB 孤儿产物；docs/ 平铺已部分解决（本轮），但 7 个数据文件仍滞留 docs/（`diagnose_trajectories.py` 硬编码引用，需随代码一起迁移）；README `WORKLOG.md` 引用失效 | SP §4/P3 | **P3** |
| **T12** | Prompt 版本管理 | prompt 为根目录裸 `.md` 文件，靠 `_v3/_simple` 文件名区分版本与适配模型 | SP §4 | **P2** |

**合并去重说明**：三份文档共 24 个问题条目，合并为 12 个主题。主要合并：GA-G1+G10→T4（抽象与结果模式一体两面）、GA-G5+G12→T7（同属安全）、GA-G6+G11→T8（同属扩展性）、GA-G8+G9→T9（同属评测可信度）、RD 全部条目→T5（RD 本身是同一主题的设计稿）、SP 的文件归类/映射表 → T6/T11 的执行细节载体。

## 2. 优先级排序逻辑

| 排序依据 | 体现 |
|---|---|
| **阻塞关系最先** | T1 不做，`git mv` 保历史、逐 step revert、tag 基线全部失效 → 一切重构的前提 |
| **止血次之** | T2/T3 不做，实验时间浪费且结果不可比，后续所有评测数据贬值 |
| **收益/成本比** | G2 resume 与 G3 cost 是"小改动大止血"；沙箱（T7）是安全红线 |
| **地基先于装修** | T4/T6 的抽象完成后再做 T5 拆分，迁移阻力最小（RD 的 step 顺序已遵循此原则） |
| **门禁恒常** | 每个里程碑完成标准：214 个 pytest 全绿 + 对应 smoke 脚本通过 |

## 3. 里程碑路线（估期按 1 人全职）

| 里程碑 | 内容 | 覆盖主题 | 完成门禁 |
|---|---|---|---|
| **M0 · 止血（本周）** | ① 提交 `tools/`、`tests/__init__.py`、处置 6 个未提交文件；② 厘清 `test` vs `master` 基线并打首个 tag；③ 最小 CI（pytest 门禁）+ 补 conftest 缺口；④ **resume**（借鉴上级仓库 `batch_generate_trajectories.py` 的 metadata 续跑模式）；⑤ **token/成本统计**（`llm_client` 统一收口 usage） | T1, T2 | pytest 214 绿；中断 run 可续跑并复现原有结果文件个数 |
| **M1 · 可复现与地基（第 2–3 周）** | ① seed 全链路 + LLM/HTTP 磁盘缓存（replay 模式）；② benchmark registry（先声明式注册 BrowseComp，再拆 `run_*` 入口为统一 CLI）；③ 统一 results schema + run spec；④ pyproject 化 + sys.path 清零 | T3, T4, T6(部分) | 同一 run 重放 byte-level 一致；`pip install -e .` 可用 |
| **M2 · 核心重构（第 4–6 周）** | god-object 拆分 + contract 层 + LLM 层规整（按 RD 的 step 序列执行，step 编号不变）；双 recorder 合并 | T5 | RD 既定回归门禁：逐 step pytest 绿 + 轨迹字段对比无 diff |
| **M3 · 严谨与安全（第 7–8 周）** | ① 代码执行沙箱（docker/e2b，断网选项）；② 统计：CI/bootstrap + seed 重复方差聚合；③ judge 人工校准基线；④ span 级 tracing（先 OTEL/JSON span 落盘，可选 Langfuse） | T7(沙箱), T9, T10 | 沙箱内执行无宿主文件系统写权限；两份独立 run 报告附置信区间 |
| **M4+ · 扩展与收口（后续）** | async 化与并发治理、guardrails、prompt registry（T12）、分布式；docs/ 数据文件随代码迁移 + README 深度瘦身（SP P3 收口） | T8, T7(其余), T11, T12 | 永不阻塞主线，按价值插单 |

**M0 状态（✅ 全部完成，`feat/m0-harness-hardening`）**：

- ✅ tag `m0-baseline`（基线锚点）+ `tools/` vendoring 切断 OffSeeker-main 路径依赖（`e0b9310`）
- ✅ 最小 CI 门禁 `.github/workflows/pytest-gate.yml` + 补 conftest patch 缺口（`581a834`）
- ✅ resume：`run_checkpoint.py` sidecar position 粒度断点，`fixed_sample`/`seed_repeats` 支持中断续跑与 `--force`（`804c15d`），模拟演练通过（中断→续跑自动跳过已完成、force 全量重跑）
- ✅ token/成本计量：`llm_usage.py` 在 `chat_completion_with_structuring` 唯一收口打点（含流式 usage、structurer 调用），结果写入 payload `llm_usage`（`97c0f65`）
- ✅ 门禁复核：pytest **241 passed**（214 基线 + 27 新增），固定样本入口语法冒烟通过

## 4. 本轮已完成的整理动作（本分支）

- ✅ 13 份一次性实验报告归档至 `docs/experiments/`（`git mv`，历史保留）
- ✅ README 全部受影响引用路径已更新（14 处）
- ✅ 新增本文（总路线）与 `GAP_ANALYSIS.md`（行业对标）
- ⏳ 数据文件（`browse_comp_test_set.csv`、seed manifests 共 7 个）**暂留** `docs/`：`diagnose_trajectories.py:13` 硬编码引用 `docs/seed123_k10_manifest.json`，迁移需与代码改动同行 → 归入 T11/M4+
- ✅ `tools/` 提交、基线厘清——已在 M0 完成（tag `m0-baseline` + vendoring `e0b9310`，见上）

## 5. 不变量（任何里程碑都不得破坏）

1. `python -m pytest tests/ -q` → 214 passed（随演进只增不减）
2. `run_browsecomp_fixed_sample.py` 固定样本（seed=123, k=10）可跑通且轨迹 schema 不漂移（蒸馏下游依赖）
3. 改造期间的 import 兼容期策略按 SP §9 执行（`__init__.py` 重导出过渡，禁止一次性断代）
