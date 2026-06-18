# 项目全量代码文件功能说明

## 📌 核心轨迹生成模块

### 1. **trajectory_agent.py** - 轨迹记录代理 ⭐️
**作用**：记录代理执行任务的完整对话过程，生成用于蒸馏训练的高质量轨迹数据

**核心功能**：
```
任务输入 → 调用 LLM API → 执行工具链 → 保存对话记录 → 输出 JSON 轨迹
```

**关键类**: `TrajectoryRecordingAgent`

**核心方法**：
- `__init()` - 初始化代理，配置 API、模型参数、工具等
- `_get_system_prompt()` - 生成系统提示词（兼容 OffSeeker）
- `_get_hint_text()` - 获取进阶提示（提高回答质量）
- `run_with_trajectory()` - 执行任务并记录完整轨迹
- `_process_tool_calls()` - 处理模型的工具调用
- `_extract_answer()` - 从 `<answer>...</answer>` 标签提取最终答案
- `_save_trajectory()` - 保存轨迹为 JSON 文件

**输入**：
- 问题字符串
- API 配置（base_url、api_key）
- 模型参数（温度、最大轮数等）

**输出**：
```json
{
  "metadata": {
    "task": "问题",
    "model": "deepseek-chat",
    "status": "completed",
    "turns": 5,
    "answer": "最终答案"
  },
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "name": "search", "content": "结果"}
  ]
}
```

**工作流**：
1. 初始化 OpenAI 兼容客户端
2. 加载工具定义（search、visit_urls、search_wiki 等）
3. 开始对话循环：
   - 发送消息给 LLM
   - 如果返回工具调用，执行工具
   - 将工具结果添加到消息历史
   - 重复直到得到答案或达到最大轮数
4. 保存完整的消息历史到 JSON 文件

---

### 2. **batch_generate_trajectories.py** - 批量轨迹生成 ⭐️
**作用**：使用多线程并发生成多个任务的轨迹，支持断点续传和智能重试

**核心功能**：
```
加载数据集 → 检查已完成任务 → 多线程生成 → 智能重试 → 保存元数据
```

**关键函数**：
- `judge_answer_semantic_match()` - 使用 LLM 判断答案的语义等价性
- `generate_single_trajectory()` - 生成单个任务的轨迹
- `main()` - 主程序，协调批量生成

**输入数据**：
```
source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl
每行格式：
{
  "question": "问题",
  "answer": "预期答案",
  "domain": "领域",
  "difficulty_level": "难度"
}
```

**输出文件**：
```
data/trajectories/{model}/
├── task_000001.json
├── task_000002.json
├── ...
└── generation_metadata.json  # 追踪重试和答案匹配情况
```

**重试机制**：
- 最多重试 2 次
- 仅在 `status == "max_turns_reached"` 或出错时重试
- **已完成但答案错误：不重试**（避免浪费 API 调用）
- 所有轨迹都被保存（包括失败的）

**断点续传**：
- 扫描已存在的 `task_*.json` 文件
- 检查 `generation_metadata.json` 中的完成状态
- 自动跳过已完成的任务
- 使用 `--force` 参数强制重新生成

**命令行参数**：
```bash
python batch_generate_trajectories.py \
    --num-samples 100        # 生成 100 个样本
    --max-workers 4          # 4 个并发线程
    --force                  # 强制重新生成（忽略已完成状态）
```

**进度追踪**：
- 使用 tqdm 显示进度条
- 打印实时统计信息（成功/失败/重试数）
- 生成完成后输出汇总统计

**输出元数据示例**：
```json
{
  "total_tasks": 100,
  "completed": 95,
  "failed": 2,
  "max_turns_reached": 3,
  "answer_match_rate": 0.87,
  "avg_turns": 6.2,
  "tasks": {
    "task_1": {
      "status": "completed",
      "attempts": 1,
      "answer_match": true,
      "ground_truth": "答案"
    }
  }
}
```

---

### 3. **convert_trajectory_to_offseeker_format.py** - 轨迹格式转换
**作用**：将 OpenAI 标准格式的轨迹转换为 OffSeeker 训练格式

**核心功能**：
```
OpenAI 轨迹格式 → OffSeeker 文本格式 → 添加完整工具定义 → 保存为训练数据
```

**关键函数**：
- `convert_trajectory()` - 单个轨迹的格式转换
- `convert_all_trajectories()` - 批量转换

**转换规则**：

1. **工具调用转换**：
```
OpenAI:
{
  "tool_calls": [
    {
      "function": {
        "name": "search",
        "arguments": "{\"query\": \"...\"}"
      }
    }
  ]
}

→ OffSeeker:
<function_call>
{"name": "search", "arguments": {"query": "..."}}
</function_call>
```

2. **消息角色转换**：
- `user` → `user`（保持不变）
- `assistant` → `assistant`（保持不变）
- `tool` → `user`（角色转换）工具结果包装成 `<result>...</result>`

3. **系统提示词注入**：
- 替换系统提示词为完整的 OffSeeker 格式
- 包含所有工具的 JSON 定义
- 包含格式化要求和提示词

**输入**：
```
data/trajectories/deepseek-chat/
├── task_000001.json
├── ...
└── generation_metadata.json
```

**输出**：
```
data/offseeker_format/deepseek-chat/
├── task_000001.json
├── ...
└── metadata.json
```

**输出格式示例**：
```json
{
  "task": "原始问题",
  "conversations": [
    {
      "role": "system",
      "content": "You are a helpful agent...<tools>{...}</tools>"
    },
    {
      "role": "user",
      "content": "问题内容"
    },
    {
      "role": "assistant",
      "content": "分析...<function_call>{...}</function_call>"
    },
    {
      "role": "user",
      "content": "<result>搜索结果</result>"
    },
    {
      "role": "assistant",
      "content": "<answer>最终答案</answer>"
    }
  ]
}
```

**命令行参数**：
```bash
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat         # 源轨迹目录
    --output data/offseeker_format/deepseek-chat    # 目标目录
    --enable-hint                                    # 添加 hint 文本
```

---

## 🧪 测试和验证模块

### 4. **test_single_task.py** - 单任务测试
**作用**：测试系统是否正常工作，用于调试配置和参数

**功能流程**：
```
加载第一个任务 → 初始化代理 → 执行代理 → 显示结果 → 比较答案
```

**具体步骤**：
1. 从 `.env` 加载 API 配置
2. 从数据集加载第一个问题
3. 显示问题、预期答案、难度、领域
4. 创建 `TrajectoryRecordingAgent` 实例
5. 执行任务并记录轨迹
6. 打印最终答案和元数据
7. 对比答案与预期结果
8. 显示轨迹统计信息

**输出示例**：
```
================================================================================
DOMAIN: FINANCE
DIFFICULTY: HARD
================================================================================
TASK:
某个复杂的金融问题...

================================================================================
GROUND TRUTH ANSWER: 具体答案
================================================================================

FINAL ANSWER:
代理给出的答案...

✓ ANSWER MATCHES GROUND TRUTH!

METADATA:
  model: deepseek-chat
  status: completed
  turns: 5
  ...
```

**使用场景**：
- ✅ 验证 API 密钥配置是否正确
- ✅ 测试模型和工具是否可用
- ✅ 调试代理行为和提示词
- ✅ 检查答案抽取逻辑

---

### 5. **verify_answer_match.py** - 答案匹配验证
**作用**：检查已生成的轨迹中是否都有 `answer_match` 字段，统计答案匹配情况

**核心功能**：
```
遍历所有轨迹文件 → 检查 answer_match 字段 → 统计结果 → 输出报告
```

**统计项**：
- 有答案且有 answer_match 的数量
- 有答案但缺少 answer_match 的数量
- 没有答案的数量
- 列出缺少 answer_match 字段的文件

**输出示例**：
```
Total files checked: 100
Has answer + has answer_match: 87
Has answer + NO answer_match: 10
No answer: 3

Files missing answer_match (10):
  Task 5: task_000005.json
    Answer: First 100 chars of answer...
  ...
```

**使用场景**：
- ✅ 质量检查：确保所有轨迹都有答案判别结果
- ✅ 找出需要重新判别的任务
- ✅ 生成完整性报告

---

### 6. **rejudge_answer_match.py** - 答案重新判别
**作用**：对已生成的轨迹中答案错误或缺失的任务重新进行语义判别

**流程**：
```
识别需要重新判别的任务 → 调用 LLM judge → 更新 answer_match 字段 → 统计结果
```

**处理条件**：
- 有答案但 `answer_match == None` 的任务
- 有答案但 `answer_match == False` 的任务

**LLM 判别提示词**：
```
你是一个判断两个答案是否语义等价的评判员

基础答案：{ground_truth}
模型答案：{model_answer}

判断标准：
- 应传达相同的核心信息
- 允许格式差异、额外上下文或部分匹配
- 模型答案应包含基础答案的关键信息

仅回答 YES 或 NO
```

**更新项**：
- 更新各个 task JSON 文件的 `answer_match` 字段
- 更新 `batch_summary.json` 统计
- 更新 `generation_metadata.json` 元数据

**输出**：
```
重新判别任务数: 25
其中答案正确（新判别为匹配）: 18
答案错误（判别为不匹配）: 7
整体答案正确率: 85%
```

**使用场景**：
- ✅ 改进答案质量评估
- ✅ 处理初次判别失误的情况
- ✅ 更新训练数据标签

---

## 📊 评估和基线模块

### 7. **run_baseline.py** - 基线实验运行
**作用**：在不同位置条件下（BrowseComp 数据集）运行标准基线实验，评估代理性能

**核心功能**：
```
加载 BrowseComp 数据集 → 固定 10 个问题 → 多个位置条件 → 评估答案 → 生成报告
```

**关键函数**：
- `_load_fixed_sample()` - 加载固定的 10 个测试样本
- `_save_manifest()` - 保存测试样本清单
- `run_single_baseline_task()` - 执行单个基线任务
- `main()` - 主程序

**评估指标**：
- **准确率**：模型答案是否正确
- **置信度**：模型对答案的置信度评分
- **轮数**：完成任务所需的交互轮数

**位置条件** (可能指答案在搜索结果中的位置)：
- 位置 0-9：不同的答案位置条件
- reasoner 模式：使用 deepseek-reasoner（含思考过程）

**输出结果**：
```
baseline_results/
├── seed123_position0_baseline.json
├── seed123_position1_baseline.json
├── seed123_position3_reasoner_baseline.json
└── ...
```

**结果格式**：
```json
{
  "position": 0,
  "total_tasks": 10,
  "correct": 7,
  "accuracy": 0.7,
  "avg_confidence": 85,
  "avg_turns": 5.2,
  "tasks": [
    {
      "task_id": 1,
      "correct": true,
      "confidence": 95,
      "turns": 4
    }
  ]
}
```

**使用场景**：
- ✅ 对标准数据集（BrowseComp）评估代理
- ✅ 比较不同位置条件下的性能
- ✅ 评估推理模式的效果

---

### 8. **browsecomp_eval/** - BrowseComp 评估框架

#### **browsecamp_eval.py** - 核心评估逻辑
**作用**：加载 BrowseComp 数据集，运行评估，生成评分

**关键类**：
- `BrowseCompEval` - 主评估类
- 包含加密数据解密、答案验证等逻辑

**核心模板**：
- `QUERY_TEMPLATE` - 问题格式
- `GRADER_TEMPLATE` - 评分模板

**功能**：
1. 从远程服务器加载 BrowseComp 数据集（CSV）
2. 支持采样固定大小的子集
3. 解密加密的问题和答案
4. 使用 LLM 评分答案是否正确

#### **run_browsecomp.py** - 评估运行脚本
**作用**：执行 BrowseComp 评估

#### **common.py** - 通用函数
**作用**：提供评估框架的通用工具函数

#### **eval_types.py** - 类型定义
**作用**：定义评估相关的类型和基类
- `SamplerBase` - 采样器基类
- `EvalResult` - 评估结果类型

---

## 🔧 工具和辅助模块

### 9. **deepseek_thinking_compat.py** - DeepSeek 兼容性处理
**作用**：处理 DeepSeek 推理模式（thinking）和非推理模式的兼容性

**核心功能**：
```
通过环境变量切换 deepseek-chat 和 deepseek-reasoner 模式
```

**关键函数**：
- `get_thinking_mode()` - 获取当前思考模式配置
- `resolve_effective_model()` - 根据模式确定实际使用的模型
- `build_chat_completion_kwargs()` - 构建 API 调用参数

**支持的模式**：
```bash
DEEPSEEK_THINKING_MODE=auto        # 保持模型配置不变（默认）
DEEPSEEK_THINKING_MODE=enabled     # 强制使用 deepseek-reasoner
DEEPSEEK_THINKING_MODE=disabled    # 强制使用 deepseek-chat
```

**处理逻辑**：
- `deepseek-reasoner` 不支持温度、top_p 等参数 → 自动过滤
- `deepseek-reasoner` 忽略工具定义中某些字段 → 自动清理
- 非 DeepSeek 模型：此模块无影响

**示例用法**：
```python
effective_model = resolve_effective_model("deepseek-chat")
# 如果 THINKING_MODE=enabled，返回 "deepseek-reasoner"

kwargs = build_chat_completion_kwargs(
    model_id="deepseek-chat",
    messages=[...],
    tools=[...],
    temperature=0.6,
)
# 自动根据最终模型调整参数
```

---

### 10. **organize_trajectories.py** - 轨迹组织
**作用**：按答案质量将轨迹文件分类到子目录

**功能**：
```
遍历所有轨迹 → 检查答案和匹配状态 → 移动到对应子目录
```

**分类标准**：
```
no_answer/      ← 没有答案的轨迹
answer_wrong/   ← 有答案但不对的轨迹
answer_correct/ ← 有答案且正确的轨迹
```

**使用场景**：
- ✅ 组织和管理大量轨迹文件
- ✅ 快速查找特定质量等级的轨迹
- ✅ 为后续分析准备数据

---

### 11. **tools_test_serper_queries.py** - Serper API 测试
**作用**：测试 Serper 搜索 API 的搜索能力和返回结果

**功能**：
```
发送测试查询 → 调用 Serper API → 打印返回结果 → 调试搜索
```

**测试查询示例**：
```python
[
    '"never been read to as a child" poet interview',
    '"never read to as a child" poet interview mental health',
    'never been read to as a child poet interview',
    '"Jason Kyle Howard married to Silas House"',
]
```

**输出信息**：
```
================================================================================
QUERY: "some test query"
STATUS: 200
BODY: {搜索结果前 2000 个字符}
```

**使用场景**：
- ✅ 验证 Serper API 密钥是否有效
- ✅ 测试搜索查询的效果
- ✅ 调试搜索工具问题
- ✅ 了解 API 返回格式

---

## 🔗 依赖和集成

### 12. **OffSeeker-main/** - OffSeeker 框架
**作用**：包含工具定义、提示词模板、蒸馏训练脚本

**核心子模块**：
```
OffSeeker-main/
├── inference/
│   └── src/
│       ├── tools/            # 工具定义和处理
│       ├── agents/           # 代理基类
│       └── ...
├── training_scripts/         # SFT/DPO 训练配置
├── deepforge/               # 数据合成框架
└── ...
```

---

## 📈 数据流总结

```
┌─────────────────────────────────────┐
│ source_oriented_data_systhesis/     │
│ mixed_domains_qa_with_enhance.jsonl │
└────────────┬────────────────────────┘
             │ 问题 + 预期答案
             ▼
   ┌──────────────────────────┐
   │ test_single_task.py      │ ← 单任务测试
   │ (验证配置)               │
   └────────────┬─────────────┘
                │ ✓ 配置正确
                ▼
   ┌──────────────────────────────────┐
   │ batch_generate_trajectories.py   │
   │ (多线程批量生成)                  │
   └────────────┬─────────────────────┘
                │ 轨迹 (OpenAI 格式)
                ▼
   ┌──────────────────────────────────┐
   │ verify_answer_match.py           │ ← 答案验证
   │ rejudge_answer_match.py          │ ← 重新判别
   │ organize_trajectories.py         │ ← 轨迹分类
   └────────────┬─────────────────────┘
                │ 轨迹 (已验证)
                ▼
   ┌──────────────────────────────────┐
   │ convert_trajectory_to_           │
   │ offseeker_format.py              │
   │ (格式转换)                        │
   └────────────┬─────────────────────┘
                │ 轨迹 (OffSeeker 格式)
                ▼
   ┌──────────────────────────────────┐
   │ OffSeeker-main/training_scripts/ │
   │ (蒸馏训练)                        │
   └──────────────────────────────────┘

评估流程：
   ┌──────────────────────┐
   │ run_baseline.py      │
   │ browsecomp_eval/     │
   │ (BrowseComp 评估)    │
   └──────────────────────┘
```

---

## 🎯 关键工作流

### 完整工作流示例：

**1. 初始化和测试**（5 分钟）
```bash
# 测试单个任务
python test_single_task.py
```

**2. 批量生成轨迹**（1-2 小时）
```bash
# 生成 100 个样本
python batch_generate_trajectories.py --num-samples 100 --max-workers 4
```

**3. 验证和清理数据**（10 分钟）
```bash
# 检查答案匹配情况
python verify_answer_match.py

# 重新判别答案
python rejudge_answer_match.py

# 组织轨迹文件
python organize_trajectories.py
```

**4. 格式转换**（5 分钟）
```bash
# 转换为 OffSeeker 格式
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat \
    --output data/offseeker_format/deepseek-chat \
    --enable-hint
```

**5. 训练和评估**
```bash
# 在 OffSeeker-main 中进行蒸馏训练
cd OffSeeker-main
llamafactory-cli train training_scripts/qwen3_8b_sft.yaml

# 在基准数据集上评估
python ../run_baseline.py
```

---

## 📊 配置关键参数

**`.env` 文件中的配置**：

```bash
# API 配置
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1

# 模型配置
DISTILLED_MODEL=deepseek-chat
DISTILLED_TEMPERATURE=0.6
DISTILLED_MAX_TURNS=30
DISTILLED_ENABLE_HINT=true

# 执行配置
DISTILLED_MAX_WORKERS=4
DISTILLED_QUERY_FILE=source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl
DISTILLED_NUM_SAMPLES=  # 空表示全部

# 工具 API
SERPER_API_KEY=xxx
JINA_API_KEY=xxx

# DeepSeek 兼容性
DEEPSEEK_THINKING_MODE=auto  # auto|enabled|disabled
```

---

## 💡 总结表格

| 文件 | 作用 | 输入 | 输出 | 时间 |
|------|------|------|------|------|
| trajectory_agent.py | 轨迹记录 | 问题 | 完整轨迹 JSON | 取决于问题 |
| batch_generate_trajectories.py | 批量生成 | JSONL 数据集 | 多个轨迹 + 元数据 | 1-2h (100 样本) |
| test_single_task.py | 单任务测试 | 数据集 | 控制台输出 | ~1min |
| convert_trajectory_to_offseeker_format.py | 格式转换 | OpenAI 轨迹 | OffSeeker 轨迹 | ~5min |
| verify_answer_match.py | 答案验证 | 轨迹文件 | 统计报告 | ~5min |
| rejudge_answer_match.py | 重新判别 | 轨迹 + LLM | 更新 answer_match | ~10min |
| organize_trajectories.py | 轨迹分类 | 轨迹文件 | 子目录分类 | ~5min |
| run_baseline.py | 基线评估 | BrowseComp 数据 | 评估结果 JSON | 取决于数据量 |
| tools_test_serper_queries.py | 搜索测试 | 查询列表 | API 响应 | ~1min |

