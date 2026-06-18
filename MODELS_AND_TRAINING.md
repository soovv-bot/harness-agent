# 项目模型和训练指南

## 🤖 项目中的模型

### 1. 教师模型（用于轨迹生成）

#### **DeepSeek Chat** 和 **DeepSeek Reasoner**
- **用途**：生成高质量的轨迹数据（做复杂推理任务）
- **API 方式**：通过 OpenAI 兼容 API 调用
- **配置**：
```bash
# .env 中配置
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
DISTILLED_MODEL=deepseek-chat
```

**两种模式对比**：

| 特性 | deepseek-chat | deepseek-reasoner |
|------|---------------|------------------|
| 推理深度 | 标准 | 深度思考（包含思考过程） |
| 速度 | 快 | 慢 |
| 准确性 | 好 | 优秀 |
| 支持工具调用 | ✅ | ✅ |
| 成本 | 低 | 高 |
| 适用任务 | 一般问题 | 复杂多跳推理 |

**切换模式**：
```bash
# 环境变量控制
DEEPSEEK_THINKING_MODE=auto        # 保持配置不变（默认）
DEEPSEEK_THINKING_MODE=enabled     # 强制使用 deepseek-reasoner
DEEPSEEK_THINKING_MODE=disabled    # 强制使用 deepseek-chat
```

---

### 2. 学生模型（用于蒸馏训练）

#### **Qwen 3 8B**
- **用途**：蒸馏训练后的离线推理模型
- **来源**：阿里云 Qwen 系列
- **大小**：80 亿参数
- **优点**：
  - 模型小，推理快
  - 中文支持好
  - 指令跟随能力强
  - 蒸馏后能保持接近教师模型的性能

**获取模型**：
```bash
# 从 Hugging Face 下载
huggingface-cli download Qwen/Qwen2.5-8B --local-dir ./qwen_model

# 或使用魔搭社区
modelscope download --model Qwen/Qwen2.5-8B --local_dir ./qwen_model
```

---

## 📚 训练流程

### 整体架构

```
┌──────────────────────────────────────────────────────────┐
│              蒸馏训练管道（Distillation Pipeline）        │
└──────────────────────────────────────────────────────────┘

第1步: 轨迹生成
  输入: QA 数据集 (mixed_domains_qa_with_enhance.jsonl)
  模型: DeepSeek Chat/Reasoner (教师模型)
  输出: 完整轨迹 (OpenAI 格式) → data/trajectories/

第2步: 数据验证
  检查答案匹配、验证轨迹完整性
  输出: 通过验证的轨迹

第3步: 格式转换
  输入: OpenAI 格式轨迹
  输出: OffSeeker 格式轨迹 → data/offseeker_format/
  
第4步: SFT 训练
  输入: OffSeeker 格式训练数据
  模型: Qwen 3 8B (学生模型)
  方法: 监督微调 (SFT)
  输出: 微调后的检查点 → checkpoint-sft/

第5步: DPO 训练（可选）
  输入: 偏好学习数据（选择更好的回应）
  方法: 直接偏好优化 (DPO)
  输出: 最终模型 → final_model/

第6步: 评估
  数据集: BrowseComp 基准测试
  指标: 准确率、推理轮数、计算效率
```

---

## 🎯 训练配置详解

### **SFT 训练配置** (qwen3_8b_sft.yaml)

```yaml
# 模型配置
model_name_or_path: /path/to/qwen3_8b_base    # 基础模型路径
use_unsloth_gc: true                          # 启用优化垃圾回收
seed: 42                                      # 随机种子（可重复）
enable_liger_kernel: true                     # 启用 Liger 内核优化

# 训练方法
stage: sft                                    # 阶段：SFT（监督微调）
do_train: true                                # 执行训练
finetuning_type: full                         # 全量微调（非 LoRA）
deepspeed: examples/deepspeed/ds_z3_config.json  # DeepSpeed ZeRO-3 配置

# 数据集配置
dataset: your_sft_dataset_name                # 数据集名称
template: qwen                                # 模板类型：qwen
cutoff_len: 136000                            # 最大序列长度（136K tokens）
max_samples: 200000                           # 最多使用 200K 样本
overwrite_cache: true                         # 覆盖缓存
preprocessing_num_workers: 16                 # 预处理工作线程数

# 输出配置
output_dir: /path/to/sft/checkpoint           # 输出检查点目录
logging_steps: 1                              # 每 1 步记录日志
save_steps: 150                               # 每 150 步保存检查点
plot_loss: true                               # 绘制损失曲线

# 训练参数
flash_attn: fa2                               # Flash Attention v2（加速）
per_device_train_batch_size: 1                # 每个 GPU 批大小
gradient_accumulation_steps: 8                # 梯度累积 8 步（有效批大小 = 1×8）
learning_rate: 3.0e-5                         # 学习率
num_train_epochs: 3.0                         # 训练 3 个 epoch
warmup_ratio: 0.1                             # 预热比例（10%）
weight_decay: 0.1                             # 权重衰减
lr_scheduler_type: cosine_with_min_lr         # 余弦学习率调度
lr_scheduler_kwargs:
  min_lr: 1.0e-7                              # 最小学习率

# 优化配置
bf16: true                                    # BF16 混合精度（节省显存）
ddp_timeout: 180000000                        # 分布式超时时间
sequence_parallel_size: 4                     # 序列并行大小

# 监控
report_to: wandb                              # 向 W&B 报告
run_name: qwen3_8b_sft_example                # 实验名称
```

**关键参数解释**：

| 参数 | 值 | 说明 |
|------|-----|------|
| `per_device_train_batch_size` | 1 | 单 GPU 批大小（显存有限） |
| `gradient_accumulation_steps` | 8 | 累积 8 次梯度后更新（模拟批大小 8） |
| `learning_rate` | 3.0e-5 | 较小的学习率（避免灾难性遗忘） |
| `num_train_epochs` | 3.0 | 遍历数据集 3 次 |
| `cutoff_len` | 136000 | 支持长序列（完整对话） |
| `bf16` | true | 减少显存占用 |

**有效批大小** = per_device_train_batch_size × gradient_accumulation_steps × num_gpus
```
= 1 × 8 × (GPU 数量)
```

---

### **DPO 训练配置** (qwen3_8b_dpo.yaml)

```yaml
# 模型配置
model_name_or_path: /path/to/sft/checkpoint   # 使用 SFT 微调后的模型
use_unsloth_gc: true
seed: 42
enable_liger_kernel: true

# 训练方法
stage: dpo                                    # 阶段：DPO（直接偏好优化）
do_train: true
finetuning_type: full
deepspeed: examples/deepspeed/ds_z3_config.json

# 数据集配置
dataset: your_dpo_dataset_name                # DPO 格式数据集
template: qwen
cutoff_len: 49152                             # 较短的序列（DPO 需要对比）
max_samples: 200000
preprocessing_num_workers: 16

# 输出配置
output_dir: /path/to/dpo/checkpoint           # DPO 检查点目录
logging_steps: 1
save_steps: 100                               # 更频繁保存
plot_loss: true

# 训练参数
flash_attn: fa2
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 1.0e-6                         # 学习率更小（DPO）
num_train_epochs: 1.0                         # 仅 1 个 epoch
warmup_ratio: 0.1
weight_decay: 0.1
lr_scheduler_type: cosine_with_min_lr

# 优化配置
bf16: true
ddp_timeout: 180000000
sequence_parallel_size: 8                     # 更大的序列并行

# 监控
report_to: wandb
run_name: qwen3_8b_dpo_example
```

**SFT vs DPO 对比**：

| 方面 | SFT | DPO |
|------|-----|-----|
| 目标 | 模型学习教师的行为 | 模型学习选择更好的回应 |
| 数据格式 | 教师回应 | （好回应，坏回应）对 |
| 学习率 | 3.0e-5（较大） | 1.0e-6（更小） |
| Epochs | 3 | 1 |
| 序列长度 | 136K | 49K |
| 何时使用 | 初始微调 | SFT 后的偏好优化 |

---

## 🚀 完整训练流程

### **第1步：数据准备**

#### 1.1 准备原始数据集
```bash
# 确保已有数据文件
ls -la source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl
```

数据格式：
```json
{
  "question": "复杂问题",
  "answer": "预期答案",
  "domain": "finance",
  "difficulty_level": "hard"
}
```

#### 1.2 生成轨迹数据
```bash
# 测试单个任务
python test_single_task.py

# 批量生成轨迹（约 1-2 小时/100 个样本）
python batch_generate_trajectories.py \
    --num-samples 100 \
    --max-workers 4

# 查看生成结果
ls -la data/trajectories/deepseek-chat/
```

#### 1.3 验证和清理数据
```bash
# 验证答案匹配
python verify_answer_match.py

# 重新判别错误答案
python rejudge_answer_match.py

# 分类整理轨迹
python organize_trajectories.py
```

#### 1.4 转换为 OffSeeker 格式
```bash
# 转换轨迹为训练格式
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat \
    --output data/offseeker_format/deepseek-chat \
    --enable-hint
```

输出示例：
```
data/offseeker_format/deepseek-chat/
├── task_000001.json
├── task_000002.json
└── ...
```

---

### **第2步：配置 LLaMA-Factory**

#### 2.1 安装 360-LLaMA-Factory
```bash
# 克隆官方仓库
git clone https://github.com/Qihoo360/360-LLaMA-Factory.git
cd 360-LLaMA-Factory

# 安装依赖
pip install -e .
```

#### 2.2 准备基础模型
```bash
# 下载 Qwen 3 8B 基础模型
huggingface-cli download Qwen/Qwen2.5-8B \
    --local-dir ./models/qwen3_8b_base

# 或从魔搭社区下载
modelscope download --model Qwen/Qwen2.5-8B \
    --local_dir ./models/qwen3_8b_base
```

#### 2.3 准备训练数据
```bash
# 创建数据目录
mkdir -p data/sft_data
mkdir -p data/dpo_data

# 将 OffSeeker 格式轨迹复制到数据目录
cp /path/to/offseeker_format/deepseek-chat/* data/sft_data/

# 对于 DPO，需要生成对比数据（见后续说明）
```

#### 2.4 修改训练配置文件

编辑 `training_scripts/qwen3_8b_sft.yaml`：
```yaml
# 更新路径
model_name_or_path: ./models/qwen3_8b_base
output_dir: ./output/qwen3_8b_sft

# 更新数据集（在 360-LLaMA-Factory 的 data 目录中定义）
dataset: your_sft_dataset_name
```

---

### **第3步：SFT 监督微调**

```bash
# 进入 360-LLaMA-Factory 目录
cd 360-LLaMA-Factory

# 运行 SFT 训练
llamafactory-cli train ../training_scripts/qwen3_8b_sft.yaml

# 或使用 Python API
python src/train.py ../training_scripts/qwen3_8b_sft.yaml
```

**训练监控**：
```bash
# 使用 tensorboard 监控
tensorboard --logdir ./output/qwen3_8b_sft/

# 或在 W&B 仪表盘查看
# https://wandb.ai/你的用户名/项目名
```

**预期输出**：
```
Step    Training Loss    Learning Rate
1       4.5234           3.0e-05
150     2.3421           2.8e-05
300     1.8765           2.5e-05
...
[已保存检查点到 output/qwen3_8b_sft/checkpoint-150]
```

**训练时间**：
```
单 GPU (A100): ~8-12 小时（100K 样本，3 epochs）
多 GPU (8×A100): ~1-2 小时（使用 DeepSpeed）
```

---

### **第4步：DPO 直接偏好优化（可选）**

#### 4.1 准备 DPO 数据格式

DPO 需要比较数据，格式如下：

```json
{
  "prompt": "问题",
  "chosen": "更好的回应",
  "rejected": "较差的回应"
}
```

**生成 DPO 数据的两种方法**：

**方法 1：使用多个模型生成回应对比**
```bash
# 用不同温度的 DeepSeek 生成不同质量的回应
# 温度低 (0.3) → 较好的回应
# 温度高 (0.9) → 较差的回应
```

**方法 2：从 SFT 轨迹提取**
```bash
# 从轨迹中提取：
# chosen = 回答正确的轨迹
# rejected = 回答错误的轨迹

python scripts/convert_to_dpo_format.py \
    --input data/offseeker_format/ \
    --output data/dpo_data/ \
    --correct_only true
```

#### 4.2 运行 DPO 训练

```bash
# 进入 360-LLaMA-Factory 目录
cd 360-LLaMA-Factory

# 运行 DPO 训练（必须先完成 SFT）
llamafactory-cli train ../training_scripts/qwen3_8b_dpo.yaml
```

**DPO 训练参数**：
```
学习率：1.0e-6（比 SFT 小 30 倍）
Beta：0.1（DPO 温度参数，控制对比强度）
Epochs：1（通常 DPO 只需 1 个 epoch）
```

---

### **第5步：评估和验证**

#### 5.1 在 BrowseComp 基准上评估
```bash
# 运行基线评估
python run_baseline.py \
    --model_path ./output/qwen3_8b_sft/checkpoint-final \
    --seed 123 \
    --positions 0,1,2,3,4,5

# 输出结果
baseline_results/
├── seed123_position0_baseline.json
└── ...
```

#### 5.2 查看评估结果
```bash
# 结果格式示例
{
  "position": 0,
  "total_tasks": 10,
  "correct": 8,
  "accuracy": 0.80,
  "avg_confidence": 85,
  "avg_turns": 5.2,
  "tasks": [...]
}
```

**性能指标对标**：

| 指标 | 基础模型 | SFT 后 | SFT+DPO 后 |
|------|---------|--------|-----------|
| 准确率 | ~40% | ~75% | ~82% |
| 平均轮数 | 8-10 | 5-7 | 4-6 |
| 推理速度 | 快 | 快 | 快 |

---

### **第6步：模型导出和部署**

#### 6.1 导出最终模型
```bash
# 合并 LoRA 权重（如果使用了 LoRA）
# 或直接使用检查点

# 将检查点转换为标准 HuggingFace 格式
python -m transformers.hf_bert_pretraining \
    --model_name_or_path ./output/qwen3_8b_sft/checkpoint-final \
    --save_dir ./output/qwen3_8b_sft/hf_model
```

#### 6.2 本地推理
```bash
# 使用 vLLM 启动服务器
python -m vllm.entrypoints.openai.api_server \
    --model ./output/qwen3_8b_sft/checkpoint-final \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.9 \
    --port 8000

# 调用 API
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-8b-sft",
    "messages": [{"role": "user", "content": "问题"}],
    "temperature": 0.6
  }'
```

---

## 💾 关键文件和路径

### 训练输出结构
```
output/
├── qwen3_8b_sft/
│   ├── checkpoint-150/          # 中间检查点
│   ├── checkpoint-final/        # 最终检查点
│   ├── training_args.bin        # 训练参数
│   ├── trainer_state.json       # 训练状态
│   └── runs/                    # TensorBoard 日志
│
└── qwen3_8b_dpo/
    ├── checkpoint-final/
    └── ...
```

### 数据文件路径
```
data/
├── trajectories/
│   └── deepseek-chat/           # 原始轨迹（OpenAI 格式）
│
└── offseeker_format/
    └── deepseek-chat/           # 转换后轨迹（训练格式）
```

---

## ⚙️ 硬件需求

### **最小配置**
```
GPU: 1×A100 (40GB)
内存: 128GB
存储: 500GB
时间: SFT ~12h, DPO ~4h
```

### **推荐配置**
```
GPU: 8×A100 (40GB) + DeepSpeed ZeRO-3
内存: 512GB
存储: 1TB
时间: SFT ~2h, DPO ~1h
```

### **显存优化**
```yaml
# 配置文件中的优化
bf16: true              # BF16 混合精度
flash_attn: fa2         # Flash Attention
gradient_checkpointing: true   # 梯度检查点
enable_liger_kernel: true      # Liger 优化
```

---

## 🔧 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| CUDA OOM | 批大小过大 | 减小 `per_device_train_batch_size` |
| 梯度爆炸 | 学习率过高 | 降低 `learning_rate` 或增加 `warmup_ratio` |
| 训练缓慢 | GPU 利用率低 | 增加 `gradient_accumulation_steps` |
| 模型不收敛 | 数据质量差 | 检查轨迹数据是否正确转换 |
| 答案偏离 | 灾难性遗忘 | 降低学习率或增加预热步数 |

---

## 📊 训练监控命令

```bash
# 监控 GPU 使用
watch -n 1 nvidia-smi

# 查看 TensorBoard
tensorboard --logdir ./output/qwen3_8b_sft/ --port 6006

# 查看 W&B 实验
# 在浏览器中访问：https://wandb.ai/

# 查看训练日志
tail -f ./output/qwen3_8b_sft/training_log.txt

# 计算参数量
python -c "import torch; model = torch.load('checkpoint_path'); print(sum(p.numel() for p in model.parameters()))"
```

---

## 📝 完整工作流命令速查

```bash
# 第1步：生成轨迹
python test_single_task.py
python batch_generate_trajectories.py --num-samples 100 --max-workers 4
python verify_answer_match.py
python rejudge_answer_match.py

# 第2步：转换格式
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat \
    --output data/offseeker_format/deepseek-chat \
    --enable-hint

# 第3步：SFT 训练
cd OffSeeker-main/360-LLaMA-Factory 2>/dev/null || cd 360-LLaMA-Factory
llamafactory-cli train training_scripts/qwen3_8b_sft.yaml

# 第4步：DPO 训练（可选）
llamafactory-cli train training_scripts/qwen3_8b_dpo.yaml

# 第5步：评估
python run_baseline.py

# 第6步：启动推理服务
python -m vllm.entrypoints.openai.api_server \
    --model ./output/qwen3_8b_sft/checkpoint-final \
    --port 8000
```

---

**项目使用的训练框架**：360-LLaMA-Factory  
**官方仓库**：https://github.com/Qihoo360/360-LLaMA-Factory  
**支持的模型**：Qwen, LLaMA, Mistral 等  
**训练方法**：SFT, DPO, PPO, SimPO 等

