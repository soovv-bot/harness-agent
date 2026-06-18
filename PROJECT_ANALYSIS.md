# 项目分析文档：Search Data Synthesis (轨迹录制与蒸馏系统)

## 📋 项目概述

### 项目名称
**Search Data Synthesis** - 离线研究代理轨迹记录与训练数据蒸馏系统

### 项目定位
这是 **OffSeeker** 项目的核心配套项目，专门用于：
- 从现有 QA 数据集生成完整的**代理轨迹数据**
- 记录代理在解决复杂研究任务时的完整对话过程
- 将轨迹转换为 OffSeeker 格式用于**模型蒸馏训练**
- 通过轨迹标注生成高质量的训练数据

### 项目用途
用于训练小型离线研究代理，使其具备：
- 网络搜索能力
- 多跳推理能力  
- 复杂查询理解能力
- 完整的工具使用能力

---

## 🏗️ 项目结构详解

### 一、核心模块

#### 1. **轨迹记录代理** (`trajectory_agent.py`)
**主要功能**：记录代理执行任务的完整对话过程

**工作流程**：
```
输入问题 → 调用 LLM API → 执行工具调用 → 保存轨迹 → 输出 JSON
```

**关键特性**：
- 使用 OpenAI 兼容的 API（支持 DeepSeek、OpenAI 等）
- 完全兼容 OffSeeker 的提示词和工具定义
- 支持多工具链式调用
- 自动保存完整的消息历史和工具调用

**输出格式**（OpenAI 标准）：
```json
{
  "metadata": {
    "task": "问题内容",
    "model": "deepseek-chat",
    "started_at": "ISO 8601 时间戳",
    "finished_at": "ISO 8601 时间戳",
    "status": "completed|max_turns_reached|error",
    "turns": 5
  },
  "messages": [
    {"role": "system", "content": "系统提示词"},
    {"role": "user", "content": "问题"},
    {"role": "assistant", "content": "思考过程", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "id", "name": "search", "content": "搜索结果"}
  ]
}
```

#### 2. **批量轨迹生成器** (`batch_generate_trajectories.py`)
**主要功能**：并发生成多个任务的轨迹

**核心特性**：
- 🔄 **断点续传**：自动跳过已完成的任务
- 📊 **并发处理**：使用 ThreadPoolExecutor 多线程生成
- 🎯 **智能重试**：仅在失败情况下重试（已完成但错误的答案不重试）
- 📈 **进度追踪**：实时显示生成进度和统计信息
- 🔍 **答案判别**：使用 LLM 判断答案的语义等价性

**输入数据**：
```
source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl
```
- 包含复杂域多个领域的 QA 对
- 每个样本都是需要生成轨迹的任务

**输出目录结构**：
```
data/trajectories/{model_name}/
├── task_000001.json
├── task_000002.json
├── ...
└── generation_metadata.json  # 追踪元数据（重试次数、答案、状态等）
```

**重试逻辑**：
```
- 最多重试 2 次
- 重试条件：status == "max_turns_reached" 或出错
- 已完成但答案错误：不重试
- 所有轨迹都保存（包括失败的）
```

#### 3. **格式转换器** (`convert_trajectory_to_offseeker_format.py`)
**主要功能**：将 OpenAI 格式轨迹转换为 OffSeeker 格式

**转换映射**：
```
OpenAI 格式 → OffSeeker 文本格式

1. Tool Calls 转换
   OpenAI:     {"tool_calls": [{"function": {"name": "search", "arguments": "{...}"}}]}
   OffSeeker:  <function_call>
               {"name": "search", "arguments": {...}}
               </function_call>

2. 消息角色转换
   user/assistant → 保持不变
   tool 响应 → user 角色，包装为 <result>...</result>

3. 系统提示词注入
   新增完整的 OffSeeker 系统提示词（包括工具定义）
```

**输出格式示例**：
```json
{
  "task": "复杂研究问题",
  "conversations": [
    {"role": "system", "content": "You are a helpful agent..."},
    {"role": "user", "content": "问题内容"},
    {"role": "assistant", "content": "分析思路...<function_call>..."},
    {"role": "user", "content": "<result>搜索结果</result>"},
    {"role": "assistant", "content": "<answer>最终答案</answer>"}
  ]
}
```

---

### 二、辅助模块

#### 1. **答案匹配验证** (`verify_answer_match.py`, `rejudge_answer_match.py`)
- 验证生成的答案是否与预期答案匹配
- 使用 LLM 进行语义等价性判断
- 支持批量重新判别

#### 2. **Baseline 运行器** (`run_baseline.py`)
- 在不同的位置条件下运行基线实验
- 用于评估代理性能

#### 3. **浏览完整度评估** (`browsecomp_eval/`)
- 评估代理的搜索和浏览行为完整性
- 包含多种评估指标

#### 4. **工具测试** (`tools_test_serper_queries.py`)
- 测试 Serper API 搜索功能
- 调试搜索工具

---

## 🚀 快速启动指南

### 环境配置

#### 1. 准备 Python 环境
```bash
# 使用 conda 激活环境
conda activate agent_safety

# 或者直接使用 Python 路径
/path/to/python/bin/python script.py
```

#### 2. 安装依赖
```bash
cd /Users/soovv/search_data_systhesis
pip install -r requirements.txt
```

#### 3. 配置 API 密钥（`.env` 文件）
```bash
# 模型 API 配置（默认使用 DeepSeek）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1

# 搜索和内容提取
SERPER_API_KEY=your_serper_key
JINA_API_KEY=your_jina_key

# 轨迹生成配置
DISTILLED_MODEL=deepseek-chat
DISTILLED_TEMPERATURE=0.6
DISTILLED_ENABLE_HINT=true
DISTILLED_MAX_TURNS=30
DISTILLED_MAX_WORKERS=4
```

### 基本工作流

#### 步骤 1: 生成单个任务的轨迹（测试）
```bash
python test_single_task.py
```
- 测试系统是否正常工作
- 使用数据集中的第一个问题
- 查看完整的轨迹输出

#### 步骤 2: 批量生成轨迹
```bash
# 生成 100 个样本的轨迹，最多 4 个并发进程
python batch_generate_trajectories.py \
    --num-samples 100 \
    --max-workers 4

# 仅生成前 10 个样本
python batch_generate_trajectories.py \
    --num-samples 10 \
    --max-workers 2
```

**支持的选项**：
```
--num-samples N           生成 N 个样本（默认全部）
--max-workers N           并发线程数（默认 4）
--force                   强制重新生成所有任务（忽略已完成状态）
```

#### 步骤 3: 转换为 OffSeeker 格式
```bash
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat \
    --output data/offseeker_format/deepseek-chat \
    --enable-hint
```

**选项说明**：
```
--input DIR               源轨迹目录（OpenAI 格式）
--output DIR              目标目录（OffSeeker 格式）
--enable-hint             是否添加 OffSeeker hint 文本
```

#### 步骤 4: 验证答案匹配
```bash
# 验证生成的答案质量
python verify_answer_match.py

# 重新判别（使用最新的 LLM）
python rejudge_answer_match.py
```

---

## 📊 数据流

```
┌─────────────────────────────────────────────────────┐
│ 输入数据                                              │
│ source_oriented_data_systhesis/data/                 │
│ mixed_domains_qa_with_enhance.jsonl                  │
└────────────────┬────────────────────────────────────┘
                 │ {问题, 预期答案}
                 ▼
        ┌────────────────────┐
        │ 批量轨迹生成       │
        │ batch_generate_    │
        │ trajectories.py    │
        └────────┬───────────┘
                 │ 重试/续传逻辑
                 ▼
        ┌────────────────────┐
        │ 轨迹记录代理       │
        │ trajectory_agent.py│
        └────────┬───────────┘
                 │ LLM API 调用
                 │ 工具执行
                 ▼
        ┌────────────────────┐
        │ 保存轨迹           │
        │ (OpenAI 格式)      │
        │ task_XXXXXX.json   │
        └────────┬───────────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
      ┌──────────┐  ┌─────────────┐
      │ 验证答案 │  │ 格式转换器  │
      │ verify_  │  │ convert_    │
      │ answer   │  │ trajectory  │
      └────┬─────┘  └──────┬──────┘
           │                │
           ▼                ▼
      ┌──────────┐  ┌─────────────────────┐
      │ 答案质量 │  │ OffSeeker 格式      │
      │ 统计     │  │ (训练数据)          │
      └──────────┘  └─────────────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │ 蒸馏训练         │
                    │ (360-LLaMA-      │
                    │ Factory)         │
                    └──────────────────┘
```

---

## 🛠️ 关键组件解析

### 工具系统

代理支持以下工具：
1. **search** - Google 搜索（通过 Serper API）
2. **visit_urls** - 访问和提取网页内容（通过 Jina API）
3. **search_wiki** - 维基百科搜索
4. **execute_code** - 代码执行能力

### 模型配置

| 用途 | 配置项 | 默认值 |
|------|--------|--------|
| 轨迹记录 | `DISTILLED_MODEL` | deepseek-chat |
| 温度控制 | `DISTILLED_TEMPERATURE` | 0.6 |
| 最大轮数 | `DISTILLED_MAX_TURNS` | 30 |
| 答案判别 | `ANSWER_JUDGE_MODEL` | deepseek-chat |
| 并发数 | `DISTILLED_MAX_WORKERS` | 4 |

### 状态跟踪

轨迹可能的状态：
- **completed** - 成功完成，获得答案
- **max_turns_reached** - 达到最大轮数限制
- **error** - 执行出错（网络、API 等）

---

## 💾 输出物

### 生成的文件结构

```
data/
├── trajectories/
│   ├── deepseek-chat/
│   │   ├── task_000001.json      # 完整轨迹（OpenAI 格式）
│   │   ├── task_000002.json
│   │   ├── ...
│   │   └── generation_metadata.json  # 统计和重试信息
│   │
│   └── generation_summary.json   # 全局汇总
│
├── offseeker_format/
│   └── deepseek-chat/
│       ├── task_000001.json      # 转换后的轨迹（OffSeeker 格式）
│       ├── task_000002.json
│       └── ...
│
└── answers/
    └── model_answers.jsonl       # 模型答案和判别结果
```

### 轨迹文件示例

**OpenAI 格式** (task_000001.json)：
```json
{
  "metadata": {
    "task": "What is the capital of France?",
    "model": "deepseek-chat",
    "started_at": "2024-01-15T10:30:00Z",
    "finished_at": "2024-01-15T10:32:15Z",
    "status": "completed",
    "turns": 3,
    "answer_match": true,
    "ground_truth": "Paris",
    "model_answer": "The capital of France is Paris"
  },
  "messages": [
    {"role": "system", "content": "You are a helpful search agent..."},
    {"role": "user", "content": "What is the capital of France?"},
    {"role": "assistant", "content": "I'll search for this information...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_123", "name": "search", "content": "Search results..."},
    {"role": "assistant", "content": "The capital of France is Paris."}
  ]
}
```

---

## 🔍 监控和调试

### 日志输出
- 使用 `loguru` 库进行结构化日志
- 日志包含完整的执行跟踪

### 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|--------|---------|
| API 密钥错误 | `.env` 配置不正确 | 检查 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` |
| 搜索失败 | Serper API 额度用尽 | 检查 `SERPER_API_KEY` 或升级账户 |
| 内容提取失败 | Jina API 问题 | 验证 `JINA_API_KEY`，降级为 html2text |
| 轨迹生成缓慢 | 并发数不足 | 增加 `DISTILLED_MAX_WORKERS` |
| 答案不匹配 | 语义差异 | 检查 `ANSWER_JUDGE_MODEL` 的判别结果 |

---

## 📈 性能指标

### 关键指标

| 指标 | 描述 | 目标值 |
|------|------|--------|
| 答案准确率 | 模型答案与预期答案的语义匹配率 | > 80% |
| 平均轮数 | 完成任务的平均轮数 | < 10 |
| 吞吐量 | 每秒生成的轨迹数 | 取决于硬件 |
| 重试率 | 需要重试的任务比例 | < 5% |

### 统计信息

生成完成后可查看 `generation_metadata.json`：
```json
{
  "total_tasks": 100,
  "completed": 95,
  "failed": 2,
  "max_turns_reached": 3,
  "answer_match_rate": 0.87,
  "avg_turns": 6.2,
  "total_retries": 5,
  "generation_time_seconds": 3600
}
```

---

## 🔄 工作流示例

### 完整的轨迹生成 → 训练流程

```bash
# 1. 测试单个任务
python test_single_task.py
# → 查看是否有错误，调整配置

# 2. 生成前 50 个样本的轨迹
python batch_generate_trajectories.py --num-samples 50 --max-workers 4
# → data/trajectories/deepseek-chat/ 目录

# 3. 验证答案质量
python verify_answer_match.py
# → 检查答案匹配率

# 4. 转换为 OffSeeker 格式
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat \
    --output data/offseeker_format/deepseek-chat \
    --enable-hint
# → data/offseeker_format/deepseek-chat/ 目录

# 5. 用于蒸馏训练（在 OffSeeker-main 中）
cd OffSeeker-main
llamafactory-cli train training_scripts/qwen3_8b_sft.yaml \
    --data_path ../data/offseeker_format/deepseek-chat
```

---

## 📚 依赖项

### Python 包
- **openai** >= 1.0.0 - API 客户端
- **transformers** >= 4.30.0 - NLP 模型
- **loguru** >= 0.7.0 - 日志
- **python-dotenv** >= 1.0.0 - 环境变量
- **tqdm** - 进度条
- **requests** - HTTP 请求
- **beautifulsoup4** - HTML 解析

### 外部服务
- **DeepSeek API** - 主模型 API
- **Serper API** - 搜索引擎
- **Jina API** - 网页内容提取
- **OffSeeker-main** - 工具定义和蒸馏训练框架

---

## 🎯 设计特点

### 1. 模块化设计
- 轨迹记录和格式转换分离
- 易于维护和扩展

### 2. 容错机制
- 断点续传支持
- 智能重试逻辑
- 所有轨迹都保存

### 3. 多模型支持
- OpenAI API 兼容
- 支持 DeepSeek、OpenAI 等多个提供商

### 4. 完整的数据追踪
- 元数据记录每个任务的状态
- 便于分析和调试

---

## 📝 注意事项

1. **API 成本** - 批量生成轨迹会产生 API 调用费用，注意预算
2. **网络依赖** - 需要稳定的互联网连接访问外部 API
3. **执行时间** - 大规模生成可能耗时数小时
4. **存储空间** - 每个轨迹文件约 10-50KB，1000 个轨迹需要 10-50MB

---

## 🤝 集成说明

本项目与 OffSeeker 的集成：
- 工具定义兼容
- 输出格式可直接用于 OffSeeker 训练
- 共享 API 配置和模型定义
- 轨迹格式符合 OffSeeker 期望

---

**项目维护者**: OffSeeker Team  
**最后更新**: 2024-01-15  
**文档版本**: 1.0
