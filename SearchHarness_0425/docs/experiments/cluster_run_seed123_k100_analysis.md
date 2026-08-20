# BrowseComp 100-Sample 评测结果分析报告

## 1. 执行命令

```bash
python run_browsecomp_fixed_sample.py \
  --seed 123 \
  --sample-size 100 \
  --positions 0-99 \
  --output results/cluster_run_seed123_k100.json \
  --trajectory-dir logs/cluster_run_seed123_k100 \
  --max-iterations 6 \
  --max-crawl-calls 30 \
  --max-planner-searches 10 \
  --max-executor-searches 20 \
  --max-total-searches 120
```

## 2. 运行环境与配置

| 参数 | 值 |
|------|-----|
| 随机种子 | 123 |
| 采样数量 | 100 |
| 采样位置 | 0–99（全量） |
| 主模型 | deepseek-chat |
| 执行器模型 | deepseek-chat |
| 评分模型 | gpt-4o-2024-11-20 |
| 最大迭代轮次 | 6 |
| 最大爬取调用数 | 30 |
| 规划器最大搜索数 | 10 |
| 执行器最大搜索数 | 20 |
| 总最大搜索数 | 120 |

## 3. 核心结论

### 3.1 准确率

| 评分来源 | 正确数 | 准确率 |
|----------|--------|--------|
| 原始评分（运行时） | 0 / 100 | **0.0%** |
| 重新评分（regraded） | 4 / 100 | **4.0%** |

原始评分为 0% 的原因是：运行时评分器（grader）使用 `gpt-4o-2024-11-20` 模型，但 API 端点仅支持 `deepseek-v4-pro` / `deepseek-v4-flash`，导致全部 22 个实际执行任务的评分返回 **400 错误**（模型名不匹配）。后续 78 个任务因 API 余额耗尽返回 **402 错误**。

重新评分使用独立的 API 端点（`https://chatapi.zjt66.top/v1`）和 `gpt-4o-2024-11-20` 模型完成，得到 4 个正确答案。

### 3.2 关键问题：77 个任务未执行

100 个任务中仅 **23 个**（task 0–22）实际执行了搜索流程，其余 **77 个**（task 23–99）在启动后约 3–4 秒内即以 `no_subtask` 原因终止，未产生任何搜索查询、候选答案或爬取操作。

**根本原因**：API 账户余额在 task 22 执行完毕后耗尽（402 Insufficient Balance），导致 task 23 起的 LLM 调用全部失败。Planner 无法生成可执行的子任务（subtask），Pipeline 在 iteration 0 即以 `no_subtask` 终止。

## 4. 详细统计分析

### 4.1 执行状态分布

| Pipeline 状态 | 数量 | 占比 |
|---------------|------|------|
| `finished`（正常完成） | 6 | 6% |
| `unfinished`（未完成） | 94 | 94% |

其中 `unfinished` 包含：
- 17 个实际执行但未在预算内收敛的任务（task 0–22 中除去 6 个 finished）
- 77 个因 API 余额耗尽而瞬间失败的任务（task 23–99）

### 4.2 时间统计

| 指标 | 值 |
|------|-----|
| 总墙钟时间 | 88,172.7 秒（**24.5 小时**） |
| 实际执行任务数（elapsed > 60s） | 23 |
| 实际执行总耗时 | 87,856 秒（24.4 小时） |
| 瞬间失败任务数（elapsed ≤ 10s） | 77 |
| 瞬间失败总耗时 | 305 秒 |
| 单任务平均耗时（实际执行） | 3,820 秒（**63.7 分钟**） |
| 最短实际执行 | 1,819 秒（30.3 分钟，task 15） |
| 最长实际执行 | 10,277 秒（171.3 分钟，task 19） |

### 4.3 实际执行任务（task 0–22）的资源使用

| 指标 | 总量 | 平均/任务 |
|------|------|-----------|
| LLM 对话消息总数 | 7,943 | 345.3 |
| 搜索查询总数 | 167 | 7.3 |
| 候选答案总数 | 18 | 0.8 |
| 访问域名总数 | 38 | 1.7 |
| 爬取 URL 总数 | 57 | 2.5 |
| 迭代轮次范围 | 3–7 | — |

**注意**：仅 task 0、15、22 三个任务产生了有效的搜索查询记录（67、44、56 次），其余 20 个任务的 `query_history` 为空（`total_queries=0`），但消息数量仍然很高（200–470 条），表明这些任务的搜索活动可能未被正确记录到 `pipeline_state.query_history` 中，或者搜索通过其他路径执行。

### 4.4 停止原因分布（task 0–22）

| 停止触发器 | 数量 | 说明 |
|------------|------|------|
| `none` | 20 | 未记录明确停止原因（正常结束或未触发限制） |
| `max_crawl_calls_reached` | 2 | task 0（33/30）、task 15（42/30） |
| `max_iterations_reached` | 1 | task 22（6/6） |

### 4.5 评分错误分布

| 错误类型 | 数量 | 影响范围 |
|----------|------|----------|
| 400 — 模型名不匹配 | 22 | task 0–21（grader 请求 `gpt-4o-2024-11-20`，API 仅支持 `deepseek-v4-pro/flash`） |
| 402 — 余额不足 | 78 | task 22–99（API 账户余额耗尽） |
| 正常评分 | 0 | 无 |

**所有 100 个任务的原始评分均失败**，0 个任务获得有效评分。重新评分后修正为 4/100。

## 5. 正确答案分析（重新评分后）

### 5.1 4 个正确回答

| Task | Position | 耗时 | 问题摘要 | 正确答案 | 提取答案 |
|------|----------|------|----------|----------|----------|
| 1 | 1 | 3,136s | 图书馆员兼作家长期伴侣的全名 | Marguerite Smith | Marguerite Smith |
| 8 | 8 | 3,166s | 2013–2016年12月发布的音乐视频歌曲名 | Porz Goret | Porz Goret |
| 13 | 13 | 3,466s | 出生于拥有前五高塔城市的作者 | Baby | Baby |
| 21 | 21 | 3,205s | 1999年开始出版生涯并创办两本杂志的人 | Dianne Sutherland | Dianne Sutherland |

**共同特征**：
- 全部 4 个均为 `finished` 状态（正常完成）
- 平均耗时 3,243 秒（54 分钟），低于整体平均的 63.7 分钟
- 提取答案与正确答案完全一致（精确匹配）

### 5.2 近似正确（finished 但答案错误）

| Task | 耗时 | 正确答案 | 提取答案 | 分析 |
|------|------|----------|----------|------|
| 5 | 5,134s | In the Arms of Morpheus: The Tragic History of Laudanum, Morphine and Patent Medicine | Opium: A Portrait of the Heavenly Demon | 找到了相关主题书籍但非正确书目 |
| 10 | 4,342s | 6187 | 5900 | 数值接近但不精确（偏差 4.7%） |

## 6. 执行时间线

```
Task  0: 06-17 11:19 → 06-17 12:27  (68.1 min)  unfinished
Task  1: 06-17 12:27 → 06-17 13:20  (52.3 min)  finished ✓
Task  2: 06-17 13:20 → 06-17 14:12  (52.5 min)  unfinished
Task  3: 06-17 14:12 → 06-17 15:13  (60.9 min)  unfinished
Task  4: 06-17 15:13 → 06-17 16:53  (99.8 min)  unfinished
Task  5: 06-17 16:53 → 06-17 18:18  (85.6 min)  finished (wrong)
Task  6: 06-17 18:19 → 06-17 18:50  (31.8 min)  unfinished
Task  7: 06-17 18:50 → 06-17 19:30  (39.5 min)  unfinished
Task  8: 06-17 19:30 → 06-17 20:23  (52.8 min)  finished ✓
Task  9: 06-17 20:23 → 06-17 21:29  (66.3 min)  unfinished
Task 10: 06-17 21:29 → 06-17 22:41  (72.4 min)  finished (wrong)
Task 11: 06-17 22:41 → 06-17 23:36  (54.3 min)  unfinished
Task 12: 06-17 23:36 → 06-18 01:33 (117.7 min)  unfinished
Task 13: 06-18 01:33 → 06-18 02:31  (57.8 min)  finished ✓
Task 14: 06-18 02:31 → 06-18 03:18  (46.4 min)  unfinished
Task 15: 06-18 03:18 → 06-18 03:48  (30.3 min)  unfinished
Task 16: 06-18 03:48 → 06-18 04:26  (37.9 min)  unfinished
Task 17: 06-18 04:26 → 06-18 05:09  (42.8 min)  unfinished
Task 18: 06-18 05:09 → 06-18 06:03  (54.8 min)  unfinished
Task 19: 06-18 06:03 → 06-18 08:55 (171.3 min)  unfinished ← 最长
Task 20: 06-18 08:55 → 06-18 10:06  (71.1 min)  unfinished
Task 21: 06-18 10:06 → 06-18 10:59  (53.4 min)  finished ✓
Task 22: 06-18 10:59 → 06-18 11:44  (44.6 min)  unfinished ← 最后一个实际执行
Task 23–99: 06-18 11:44 → 06-18 11:49  (~4s each)  全部瞬间失败 (402 余额不足)
```

**总运行时间**：2026-06-17 11:19 → 2026-06-18 11:49，约 24.5 小时。

任务为串行执行（无并行），每个任务完成后立即开始下一个。

## 7. 问题诊断与根因分析

### 7.1 评分器模型配置错误（影响 22 个任务）

**现象**：task 0–21 的评分均返回 HTTP 400 错误：
```
The supported API model names are deepseek-v4-pro or deepseek-v4-flash,
but you passed gpt-4o-2024-11-20.
```

**根因**：`GRADER_MODEL_NAME` 设置为 `gpt-4o-2024-11-20`，但评分 API 端点（`OPENAI_BASE_URL`）指向的 DeepSeek 兼容服务不支持该模型名。

**影响**：22 个实际执行的任务在运行时均未获得有效评分，`correct_count` 显示为 0。通过重新评分修复后实际正确 4 个。

**建议**：
- 设置 `GRADER_OPENAI_BASE_URL` 指向支持 `gpt-4o-2024-11-20` 的 API 端点
- 或将 `GRADER_MODEL_NAME` 修改为 API 端点支持的模型名（如 `deepseek-v4-pro`）

### 7.2 API 余额耗尽（影响 78 个任务）

**现象**：task 22 的评分返回 HTTP 402（Insufficient Balance），此后 task 23–99 全部在 3–4 秒内以 `no_subtask` 终止。

**根因**：API 账户余额在 task 22 执行过程中耗尽。task 23 起，Planner 的 LLM 调用失败，无法生成可执行子任务，Pipeline 在 iteration 0 即终止。

**影响**：77 个任务完全没有执行，浪费了 77/100 的采样配额。

**建议**：
- 运行前确认 API 账户余额充足（按每任务约 3,800 秒、200–500 条消息的 LLM 调用量估算）
- 在脚本中增加余额预检机制
- 考虑添加失败任务的自动重跑逻辑

### 7.3 搜索查询记录缺失

**现象**：23 个实际执行的任务中，仅 3 个（task 0、15、22）在 `pipeline_state.query_history` 中记录了搜索查询，其余 20 个的 `total_queries=0`，但消息数量高达 200–470 条。

**可能原因**：
- 搜索查询通过 executor 子任务内部执行，未回写到 planner 的 `query_history`
- Pipeline 状态序列化逻辑存在遗漏
- 搜索可能通过非标准路径（如直接在对话中）执行

**建议**：检查 `pipeline_state` 的更新逻辑，确保所有搜索活动被正确记录。

### 7.4 任务串行执行导致总耗时长

**现象**：100 个任务串行执行，23 个实际执行任务耗时 24.4 小时，平均每任务 63.7 分钟。

**建议**：考虑使用 `ThreadPoolExecutor` 并行执行（脚本已导入但未在 100-sample 模式下启用），在 API 速率限制允许的情况下可显著缩短总耗时。

## 8. 有效准确率估算

由于 77 个任务未实际执行，基于 23 个实际执行的任务计算有效准确率：

| 指标 | 值 |
|------|-----|
| 实际执行任务数 | 23 |
| 其中正确数（重新评分后） | 4 |
| 有效准确率 | **17.4%**（4/23） |
| 其中 finished 数 | 6 |
| finished 中正确数 | 4 |
| finished 准确率 | **66.7%**（4/6） |

**关键发现**：当 Pipeline 能够正常完成（`finished` 状态）时，准确率达到 66.7%，说明 agent 的搜索和推理能力本身不弱，主要瓶颈在于任务完成率（仅 6/23 = 26.1% 的任务能够在预算内收敛）。

## 9. 结论与建议

### 9.1 当前运行总结

- **名义准确率**：4.0%（4/100，重新评分后）
- **有效准确率**：17.4%（4/23，仅计算实际执行的任务）
- **完成率**：6.0%（6/100 finished），有效完成率 26.1%（6/23）
- **总耗时**：24.5 小时
- **主要瓶颈**：API 余额耗尽导致 77% 任务未执行；评分器配置错误导致原始评分为 0

### 9.2 改进建议

| 优先级 | 建议 | 预期影响 |
|--------|------|----------|
| P0 | 确保 API 账户余额充足或设置自动充值 | 避免任务中途失败 |
| P0 | 修复评分器模型配置（`GRADER_MODEL_NAME` 或 `GRADER_OPENAI_BASE_URL`） | 获得准确的运行时评分 |
| P1 | 增加失败任务自动重跑机制（已有 `--force` 参数支持） | 提高 有效样本量 |
| P1 | 增大 `max_iterations`（当前 6 偏保守，20 个任务因预算耗尽而 unfinished） | 提高任务完成率 |
| P2 | 启用并行执行（`ThreadPoolExecutor`） | 缩短总运行时间 |
| P2 | 排查 `query_history` 记录缺失问题 | 改进可观测性 |
| P3 | 对比 BrowseComp 基线（OpenAI 报告 GPT-4o 约 10%+） | 评估竞争力 |

### 9.3 重跑建议

完成 API 余额充值和评分器配置修复后，可使用以下命令重跑 task 23–99：

```bash
python run_browsecomp_fixed_sample.py \
  --seed 123 \
  --sample-size 100 \
  --positions 23-99 \
  --output results/cluster_run_seed123_k100_part2.json \
  --trajectory-dir logs/cluster_run_seed123_k100_part2 \
  --max-iterations 6 \
  --max-crawl-calls 30 \
  --max-planner-searches 10 \
  --max-executor-searches 20 \
  --max-total-searches 120
```

或使用 `--force` 全量重跑（会覆盖已有结果）。

---

*报告生成时间：2026-06-22*
*数据来源：`results/cluster_run_seed123_k100.json`、`results/cluster_run_seed123_k100_regraded.json`、`logs/cluster_run_seed123_k100/deepseek-chat/`*
