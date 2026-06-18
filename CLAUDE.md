# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**OffSeeker** is a research project for offline training of deep research agents for web search and multi-hop reasoning. It consists of three main components:

1. **DeepForge** (`deepforge/`) - Data synthesis framework that generates complex research queries by constructing entity-centric knowledge graphs
2. **Training Scripts** (`training_scripts/`) - SFT/DPO training configurations using 360-LLaMA-Factory
3. **Inference** (`inference/`) - Agent framework for web-based research tasks with tool integration

**This Repository** - Trajectory recording for distillation:
- Records complete agent trajectories using OpenAI-style API
- Generates training data from `source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl`
- Converts trajectories to OffSeeker format for distillation training

## Environment Setup

### Conda Environment
- **Environment name**: `agent_safety`
- **Environment path**: `D:\anaconda3\envs\agent_safety`
- **Python path**: `D:\anaconda3\envs\agent_safety\python.exe`

### Usage
```bash
# Activate environment
conda activate agent_safety

# Or use python directly
D:\anaconda3\envs\agent_safety\python.exe script.py
```

## Common Commands

### Installation
```bash
pip install -r requirements.txt
```

### DeepForge Data Synthesis Pipeline
The 6-step pipeline generates research QA pairs from scratch. Start with the demo for understanding:

```bash
cd deepforge

# Demo workflow (recommended for beginners)
python scripts/demo.py

# Full production pipeline
# Step 1: Generate URLs from random nouns
python scripts/generate_urls.py --num-nouns 100 --urls-per-noun 10 --output data/urls.jsonl

# Step 2: Extract seed entities from URLs
python scripts/generate_seed_entities.py --input data/urls.jsonl --output data/seed_entities.jsonl --num-urls 50

# Step 3 & 4: Generate entity graphs and QA pairs
python scripts/generate_qa.py --seed-entities tmp/seed_entities.json --output data/qa_pairs_all.jsonl --graphs tmp/seed_entities_graph.jsonl

# Step 5: Difficulty enhancement (optional)
python scripts/enhance_difficulty.py --input data/qa_pairs_all.jsonl --output data/qa_pairs_enhanced.jsonl

# Step 6: Quality filtering (optional)
python scripts/filter_quality.py --input data/qa_pairs_enhanced.jsonl --output data/qa_pairs_hard.jsonl
```

### Inference and Evaluation
```bash
cd inference

# Start vLLM server (supports tensor parallelism across GPUs)
python scripts/run_vllm_server.py \
    --model_path /path/to/model \
    --model_name model_name \
    --start_port 8010 \
    --num_instances 1 \
    --tensor_parallel_size 2

# Run evaluation
./run_evaluation.sh \
    --benchmark_name benchmark_file \
    --vllm_server_ip 127.0.0.1 \
    --vllm_server_ports 8010 \
    --vllm_model_name model_name \
    --max_workers 8 \
    --save_path_suffix test \
    --tokenizer_path /path/to/tokenizer \
    --max_context_length 131072
```

### Training (via 360-LLaMA-Factory)
```bash
llamafactory-cli train training_scripts/qwen3_8b_sft.yaml
llamafactory-cli train training_scripts/qwen3_8b_dpo.yaml
```

### Trajectory Generation (This Repository)
```bash
# Single task test (for debugging)
python test_single_task.py

# Batch generate trajectories with retry support
python batch_generate_trajectories.py --num-samples 100 --max-workers 4

# Resume from previous run (skips completed tasks)
python batch_generate_trajectories.py --num-samples 100 --max-workers 4

# Force re-run all tasks
python batch_generate_trajectories.py --num-samples 100 --max-workers 4 --force

# Convert trajectories to OffSeeker format for training
python convert_trajectory_to_offseeker_format.py \
    --input data/trajectories/deepseek-chat \
    --output data/offseeker_format/deepseek-chat \
    --enable-hint
```

## Project Structure (This Repository)

```
search_data_systhesis/
├── OffSeeker-main/              # Original OffSeeker framework (reference)
├── source_oriented_data_systhesis/  # Data source
│   └── data/
│       └── mixed_domains_qa_with_enhance.jsonl
├── data/
│   └── trajectories/            # Generated trajectories (OpenAI format)
│       ├── deepseek-chat/
│       │   ├── task_000001.json
│       │   └── ...
│       └── generation_metadata.json  # Retry tracking
├── trajectory_agent.py          # Core trajectory recording agent
├── batch_generate_trajectories.py  # Batch generation with retry & resume
├── convert_trajectory_to_offseeker_format.py  # Format conversion for training
├── test_single_task.py          # Single task test (debugging)
└── .env                         # Environment variables
```

## Trajectory Format

### OpenAI Format (Generated)
```json
{
  "metadata": {
    "task": "...",
    "model": "deepseek-chat",
    "started_at": "...",
    "finished_at": "...",
    "status": "completed",
    "turns": 5
  },
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "任务"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "name": "search", "content": "..."}
  ]
}
```

### OffSeeker Format (For Training)
```json
{
  "task": "...",
  "conversations": [
    {"role": "system", "content": "You are a helpful agent...<tools>...</tools>..."},
    {"role": "user", "content": "任务"},
    {"role": "assistant", "content": "...<function_call>\n{\"name\": \"search\", ...}\n</function_call>"},
    {"role": "user", "content": "<result>\nTool: search\nResult: ...\n</result>"}
  ]
}
```

## Retry & Resume Logic

- **Max retries**: 2 attempts per task
- **Retry condition**: Only when `status == "max_turns_reached"` or error
- **No retry for wrong answers**: If `status == "completed"` but answer is wrong, no retry
- **Failed trajectories saved**: All trajectories are saved, including failed ones
- **Metadata tracking**: `generation_metadata.json` tracks attempts, answers, and status per task
- **Resume support**: Automatically skips completed tasks on next run

## Architecture

### DeepForge Pipeline Architecture

The data synthesis follows a 6-stage pipeline:

1. **URL Generation** - Random noun generation → Serper API search → URL collection
2. **Entity Extraction** - URL crawling (Jina/html2text fallback) → long-tail entity extraction
3. **Entity Graph Construction** - Multi-hop exploration using Gemini agent with tools
4. **QA Generation** - Complex question generation from entity graphs
5. **Difficulty Enhancement** - Remove clues, increase ambiguity
6. **Quality Filtering** - Filter out questions that are too easy

**Key Components:**
- `APICaller` (`deepforge/api/`) - Unified interface for vLLM, OpenAI, DeepSeek, Gemini APIs
- `Entity`/`EntityGraph` (`deepforge/src/entities/`) - Knowledge representation data structures
- `GeminiAgent` (`deepforge/src/agents/`) - Tool-using agent for entity exploration
- Tool schemas in `deepforge/src/tools/` - `search_google`, `crawl_url_content`, `search_wiki`

### Inference Agent Architecture

**BaseSearchAgent** (`inference/src/agents/base_agent.py`) - Abstract base class providing:
- Conversation context and trajectory management
- Token counting with context length management
- Tool call processing using `<function_call>...</function_call>` tags
- Answer extraction from `<answer>...</answer>` tags
- Session restart for long-running tasks

**VLLMSearchAgent** (`inference/src/agents/vllm_agent.py`) - Concrete implementation:
- Connects to local vLLM servers via OpenAI-compatible API
- Load balancing across multiple server instances
- Retry logic with exponential backoff

**Available Tools:** `search`, `visit_urls`, `search_wiki`, `execute_code`

### Configuration System

All configuration is centralized in `deepforge/config/settings.py` using dataclasses:
- `APIConfig` - API endpoints, model names, authentication
- `PathConfig` - Input/output file paths
- `ConcurrencyConfig` - Worker counts for each pipeline stage
- `GenerationConfig` - QA generation parameters

Configuration can be loaded from YAML (`config.yaml`) or overridden via environment variables (`.env`).

## Conventions

### Response Format Tags
- **Tool Calls**: `<function_call>...</function_call>` (DeepForge) or `<tool_call>...</tool_call>` (Inference)
- **Thinking**: `<thinking>...</thinking>`
- **Answers**: `<answer>...</answer>`
- **Results**: `<result>...</result>` (DeepForge exploration)

### Environment Variables
Required in `deepforge/.env`:
- `SERPER_API_KEY` - Google Search (required)
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` - Gemini/OpenAI endpoint (required)
- `JINA_API_KEY` - Content extraction (required)
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` - DeepSeek (optional)

### Error Handling Patterns
- `@retry(tries=10, delay=1.0, backoff=2.0)` decorator for API calls
- Graceful degradation: Jina API → html2text for crawling
- Warning logs for 429 (rate limits), Error logs for 401/403 (auth failures)

### Concurrency Patterns
- `ThreadPoolExecutor` for parallel URL crawling, Wikipedia search
- Threading locks for concurrent file writes
- Configurable worker counts per pipeline stage

## Dependencies

**Core:** openai>=1.0.0, transformers>=4.30.0, vllm==0.10.0, pydantic>=2.0.0

**Tools:** requests, httpx, beautifulsoup4, html2text, wikipedia, wikipedia-api, PyPDF2

**Utilities:** loguru>=0.7.0 (logging), python-dotenv>=1.0.0, PyYAML>=6.0.0, retry>=0.9.2

**External:** 360-LLaMA-Factory for training (https://github.com/Qihoo360/360-LLaMA-Factory)
