# Deep Research Inference Framework

This directory contains a deep research inference framework based on vLLM, supporting local deployment of open-source large language models for complex deep research tasks.

## Project Structure

```text
inference/
├── src/
│   ├── __init__.py
│   ├── agents/          # Agent implementations
│   │   ├── __init__.py
│   │   ├── base_agent.py      # Base agent abstract class
│   │   └── vllm_agent.py      # VLLM-based agent implementation
│   └── tools/           # Tool implementations
│       ├── __init__.py
│       ├── tool_processor.py  # Tool call processor
│       ├── search_tools.py    # Web search, crawling, Wikipedia tools
│       └── subprocess_interpreter.py  # Code execution tool
├── scripts/
│   ├── run_vllm_server.py   # VLLM server startup script
│   └── example_usage.py     # Usage example for VLLMSearchAgent
├── config/                  # Configuration directory (currently empty)
├── benchmark/               # Evaluation datasets
├── evaluate.py             # Batch evaluation script
├── run_evaluation.sh       # Evaluation startup script
└── README.md
```

## Quick Start

### 1. Requirements

- Python >= 3.8
- CUDA >= 11.8 (for GPU inference)
- VLLM (refer to [VLLM official documentation](https://docs.vllm.ai/))

### 2. Install Dependencies

```bash
# Install from project root directory
cd ../  # Go to project root
pip install -r requirements.txt
cd inference  # Return to inference directory
```

### 3. Configure Environment Variables

**Important**: Environment variables are now loaded uniformly through the `run_evaluation.sh` script. The `.env` file is no longer used.

Edit the `run_evaluation.sh` file to configure the following environment variables:

```bash
# VLLM Server Configuration (used by run_vllm_server.py)
export MODEL_PATH=/path/to/your/model
export MODEL_NAME=your_model_name
export TP_SIZE=2  # Tensor parallel size

# DeepSeek API Configuration (Required - for webpage extraction and answer judging)
# Get your API key from https://platform.deepseek.com/
export DEEPSEEK_API_KEY=your_deepseek_api_key

# API Keys (for search and web crawling)
export SERPER_API_KEY=your_serper_api_key  # For Google search (via Serper API)
export JINA_API_KEY=your_jina_api_key      # For web crawling (optional, defaults to html2text)

# Crawler Engine Selection
export CRAWLER_ENGINE=jina  # Options: html2text or jina (defaults to html2text if JINA_API_KEY not set)
```

**Note**: If you run Python scripts directly (without using `run_evaluation.sh`), you need to manually set these environment variables using the `export` command in your terminal.

## Usage

### 1. Start VLLM Server

**Important**: Before starting the server, determine how many GPU instances you want to run based on your available GPUs and desired tensor parallel size.

**Formula**: `num_instances = total_gpus / tensor_parallel_size`

For example:

- 2 GPUs with `tensor_parallel_size=2` → 1 instance
- 4 GPUs with `tensor_parallel_size=2` → 2 instances
- 8 GPUs with `tensor_parallel_size=2` → 4 instances
- 2 GPUs with `tensor_parallel_size=1` → 2 instances

#### Single Instance (Recommended for Small GPU Counts)

If you have 1-2 GPUs:

```bash
python scripts/run_vllm_server.py \
    --model_path /path/to/your/model \
    --model_name your_model_name \
    --start_port 8010 \
    --num_instances 1 \
    --tensor_parallel_size 1
```

Or with 2 GPUs using tensor parallelism:

```bash
python scripts/run_vllm_server.py \
    --model_path /path/to/your/model \
    --model_name your_model_name \
    --start_port 8010 \
    --num_instances 1 \
    --tensor_parallel_size 2
```

#### Multiple Instances (Load Balancing)

**Example 1: 4 GPUs, 2 instances (each using 2 GPUs)**

```bash
python scripts/run_vllm_server.py \
    --model_path /path/to/your/model \
    --model_name your_model_name \
    --start_port 8010 \
    --num_instances 2 \
    --tensor_parallel_size 2 \
    --total_gpus 4
```

This will start 2 instances on ports 8010 and 8011, each using 2 GPUs.

**Example 2: 8 GPUs, 4 instances (each using 2 GPUs)**

```bash
python scripts/run_vllm_server.py \
    --model_path /path/to/your/model \
    --model_name your_model_name \
    --start_port 8010 \
    --num_instances 4 \
    --tensor_parallel_size 2 \
    --total_gpus 8
```

This will start 4 instances on ports 8010, 8011, 8012, and 8013, each using 2 GPUs.

**Note**:

- Ports are automatically assigned starting from `--start_port` and incrementing by 1 for each instance.
- Make sure the ports you specify in the evaluation script match the ports where your VLLM servers are actually running.

### 2. Run Evaluation

Prepare your benchmark file in `benchmark/` directory.
The file should be in JSONL format, each line is a JSON object with **at least** the following fields:

- `id`: Task ID
- `question`: Question
- `answer`: Answer

#### Using run_evaluation.sh Script

**Important**: The `--vllm_server_ports` parameter must match the ports where your VLLM servers are actually running.

**Example 1: Single instance (1 server on port 8010)**

```bash
./run_evaluation.sh \
    --benchmark_name your_benchmark_file_name \
    --vllm_server_ip 127.0.0.1 \
    --vllm_server_ports 8010 \
    --vllm_model_name your_model_name \
    --max_workers 8 \
    --save_path_suffix test_run \
    --tokenizer_path /path/to/tokenizer \
    --max_context_length 131072
```

**Example 2: Multiple instances (4 servers on ports 8010-8013)**

```bash
./run_evaluation.sh \
    --benchmark_name your_benchmark_file_name \
    --vllm_server_ip 127.0.0.1 \
    --vllm_server_ports 8010,8011,8012,8013 \
    --vllm_model_name your_model_name \
    --max_workers 8 \
    --save_path_suffix test_run \
    --tokenizer_path /path/to/tokenizer \
    --max_context_length 131072
```

**Note**:

- Make sure to configure the corresponding API keys and other environment variables in `run_evaluation.sh` before running.
- The number of ports in `--vllm_server_ports` should match the number of VLLM server instances you started.
- If you specify ports that don't have running servers, the evaluation will fail with connection errors.

The `run_evaluation.sh` script will automatically:

- Set necessary environment variables (such as `DEEPSEEK_API_KEY`, `SERPER_API_KEY`, etc.)
- Configure PYTHONPATH to include the `src/` directory
- Run the evaluation script with all passed arguments

#### Direct Python Script Usage

**Important**: The `--vllm_server_ports` parameter must match the ports where your VLLM servers are actually running.

**Example: Single instance**

```bash
python evaluate.py \
    --benchmark_name your_benchmark_file_name \
    --vllm_server_ip 127.0.0.1 \
    --vllm_server_ports 8010 \
    --vllm_model_name your_model_name \
    --max_workers 8 \
    --save_path_suffix test_run \
    --tokenizer_path /path/to/tokenizer \
    --max_context_length 131072
```

**Example: Multiple instances**

```bash
python evaluate.py \
    --benchmark_name your_benchmark_file_name \
    --vllm_server_ip 127.0.0.1 \
    --vllm_server_ports 8010,8011,8012,8013 \
    --vllm_model_name your_model_name \
    --max_workers 8 \
    --save_path_suffix test_run \
    --tokenizer_path /path/to/tokenizer \
    --max_context_length 131072
```

**Note**:

- `evaluate.py` automatically configures import paths by adding the `src/` directory to `sys.path`. No need to manually set `PYTHONPATH` or install the package.
- If you run `evaluate.py` directly (without using `run_evaluation.sh`), you need to manually set environment variables (such as `DEEPSEEK_API_KEY`, `SERPER_API_KEY`, etc.).
- The number of ports in `--vllm_server_ports` should match the number of VLLM server instances you started.

### 3. Run Single Task Example

You can also use the example script to test a single task:

```bash
python scripts/example_usage.py
```

**Note**: Before running `example_usage.py`, you need to manually set environment variables (such as `VLLM_SERVER_IP`, `VLLM_SERVER_PORTS`, `VLLM_MODEL_NAME`, etc.) using the `export` command in your terminal.

## Tools

OffSeeker inference framework provides the following tools:

1. **search**: Web search using Google (via Serper API). Supports multiple queries in parallel.
2. **visit_urls**: Visit URLs and extract relevant information based on queries. Uses DeepSeek API for content extraction and summarization.
3. **search_wiki**: Search Wikipedia for entity information. Supports multiple entities in parallel.
4. **execute_code**: Execute Python code snippets in a sandboxed subprocess environment.

## Evaluation Results

Evaluation results are saved in the `results/` directory (created automatically) in JSONL format. Each result contains:

- `id`: Task ID
- `judge_result`: Judgment result (True/False) - determined by DeepSeek API judge
- `token_count`: Total number of tokens used (including all conversation turns)
- `source`: Data source (from benchmark dataset)
- `question`: Original question
- `answer`: Ground truth answer
- `model_response`: Final model response
- `trajectory`: Complete conversation trajectory (list of all conversation turns)

After running the evaluation, the script will automatically calculate and display statistics, including:

- Overall accuracy
- Accuracy by data source
- Total number of processed cases

The evaluation script supports resuming from previous runs - it automatically skips already processed tasks based on the result file.

## Usage Examples

### Using VLLMSearchAgent Programmatically

See `scripts/example_usage.py` for a complete example of how to use the `VLLMSearchAgent` in your own code.

```python
from agents.vllm_agent import VLLMSearchAgent

agent = VLLMSearchAgent(
    server_ip="127.0.0.1",
    server_port=[8010, 8011],  # Load balancing across multiple ports
    model_name="your_model_name",
    tokenizer_path="/path/to/tokenizer",
    max_context_length=262144
)

response = agent.run_loop("Your task here")
```
