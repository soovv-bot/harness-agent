"""
Batch evaluation script for Deep Research Inference
Supports evaluating benchmarks using VLLMSearchAgent
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from copy import deepcopy
from tqdm import tqdm
from loguru import logger
from openai import OpenAI

# Add src directory to Python path for direct imports
SCRIPT_DIR = Path(__file__).parent.absolute()
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tools import ALL_TOOL_SCHEMAS
from agents.vllm_agent import VLLMSearchAgent

file_lock = Lock()

# Initialize answer judge client
judger_client = None
judger_model_name = "deepseek-chat"

judger_api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
judger_base_url = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://preview.llm.tenyunc.com/v1"
if judger_api_key:
    try:
        judger_client = OpenAI(
            api_key=judger_api_key,
            base_url=judger_base_url,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize answer judger client: {e}")
else:
    logger.warning("Neither DEEPSEEK_API_KEY nor OPENAI_API_KEY is set, answer judging will be skipped")


def get_processed_data_id(save_path: str) -> set:
    """Get set of already processed data IDs."""
    processed_data_id = set()
    if not os.path.exists(save_path):
        return processed_data_id
    with open(save_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line.strip())
            processed_data_id.add(data["id"])
    return processed_data_id


def check_answer(data: dict, model_response: str) -> bool:
    """
    Check if model response is correct using DeepSeek API as judge.
    
    Args:
        data: Ground truth data with question and answer
        model_response: Model's response
        
    Returns:
        True if correct, False otherwise
    """
    if not judger_client:
        logger.warning("DeepSeek judger client not available, skipping answer check")
        return False
    
    prompt = f"""
Here is the original question: {data['question']}

Here is the model response: {model_response}

Here is the golden answer: {data['answer']}

Please check if the model response is semantically correct compared to the golden answer.
If it is, return "Yes", otherwise, return "No", enclosed in <judge>...</judge> tags.
For example, if the model's response is correct, return "<judge>Yes</judge>", otherwise, return "<judge>No</judge>".
"""
    try:
        response = judger_client.chat.completions.create(
            model=judger_model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that can check if the following answer is correct compared to the golden answer."},
                {"role": "user", "content": prompt}
            ],
        )
        raw_response = response.choices[0].message.content
        if "<judge>" in raw_response:
            judge_result = raw_response.split("<judge>")[1].split("</judge>")[0]
            if "yes" in judge_result.lower():
                return True
            else:
                return False
        else:
            logger.error(f"Judger response is not in the expected format: {raw_response}, {data['question']}")
            return False
    except Exception as e:
        logger.error(f"Error checking answer with DeepSeek API: {e}")
        return False


def build_agent(
    vllm_server_ip: str,
    vllm_server_ports: List[int],
    vllm_model_name: str,
    tokenizer_path: Optional[str] = None,
    max_context_length: int = 262144,
    **kwargs
) -> VLLMSearchAgent:
    """
    Build VLLM search agent.
    
    Args:
        vllm_server_ip: VLLM server IP address
        vllm_server_ports: List of VLLM server ports
        vllm_model_name: Model name
        tokenizer_path: Path to tokenizer
        max_context_length: Maximum context length
        **kwargs: Additional agent arguments
        
    Returns:
        VLLMSearchAgent instance
    """
    tool_schemas = "\n".join([json.dumps(schema, ensure_ascii=False, indent=2) for schema in ALL_TOOL_SCHEMAS])

    system_prompt = f"""
You are a helpful agent that can appropriately leverage the available tools to solve complex tasks.
Your response should strictly follow the format:

1. Provide an explanation for your action, which should be enclosed by <think> </think> tags.
First, review the previous steps to provide context.
Next, describe any new observations or relevant information obtained since the last step.
Finally, clearly explain your reasoning and the rationale behind your current output or decision.

2. Use the available tools to gather information or perform actions.
Tool calls should be wrapped in <tool_call> </tool_call> tags and follow the JSON format.
Then, we will extract tool call, provide tool response for you. The tool response will be enclosed by <tool_response> </tool_response> tags.

3. If you have finished the task, provide the final answer. The final answer should be enclosed by <answer> </answer> tags.
In that case, you should not output any more tool calls.

You should always dive deep into the webpage content to confirm some details.
You can flexibly use multiple search terms or URLs at once to speed up the process and enhance the breadth of your search.
Besides the given tools, you can also use multiple tool calls in sequence to solve the task comprehensively.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_schemas}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>
"""

    return VLLMSearchAgent(
        server_ip=vllm_server_ip,
        server_port=vllm_server_ports,
        model_name=vllm_model_name,
        system_prompt=system_prompt,
        enable_hint=True,
        tokenizer_path=tokenizer_path,
        max_context_length=max_context_length,
        **kwargs
    )


def process_single_task(
    agent_kwargs: Dict,
    data: dict,
    save_path: str
):
    """Process a single task."""
    prompt = f"Solve the following task: {data['question']}"

    agent = build_agent(**agent_kwargs)

    response = agent.run_loop(prompt)
    if "chat completion failed" in response:
        return

    trajectory = agent.trajectory
    judge_result = check_answer(data, response)

    logger.info(f"Ground truth: {data['answer']}, Judge result: {judge_result}")

    with file_lock:
        with open(save_path, "a", encoding="utf-8") as f:
            result_dict = {
                "id": data["id"],
                "judge_result": judge_result,
                "token_count": agent.all_token_count,
                "source": data.get("source", ""),
                "question": data["question"],
                "answer": data["answer"],
                "model_response": response,
                "trajectory": trajectory,
            }
            f.write(json.dumps(result_dict, ensure_ascii=False) + "\n")


def process_batch(
    agent_kwargs: Dict,
    data_list: list,
    save_path: str,
    max_workers: int = 10,
):
    """Process a batch of tasks."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        try:
            futures = [
                executor.submit(
                    process_single_task,
                    agent_kwargs,
                    data,
                    save_path,
                ) for data in data_list
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing tasks"):
                future.result()
        except KeyboardInterrupt:
            print("Keyboard interrupt received. Cancelling tasks...")
            for future in futures:
                future.cancel()
            executor.shutdown(wait=True)
            raise KeyboardInterrupt


def calculate_statistics(save_path: str, sample_num: Optional[int] = None):
    """Calculate and print evaluation statistics."""
    from pprint import pprint
    statistics = {}
    overall_statistics = {"total": 0, "correct": 0, "incorrect": 0}

    data_list = []
    with open(save_path, "r", encoding="utf-8") as f:
        for line in f:
            data_list.append(json.loads(line))

    if sample_num is not None:
        tmp_data_list = deepcopy(data_list)
        data_list = []
        for data in tmp_data_list:
            if int(data['id']) < sample_num:
                data_list.append(data)

    print(f"Total {len(data_list)} cases")

    for data in data_list:
        source = data.get("source", "unknown")
        if source not in statistics:
            statistics[source] = {"total": 0, "correct": 0, "incorrect": 0}
        statistics[source]["total"] += 1
        if data["judge_result"]:
            statistics[source]["correct"] += 1
            overall_statistics["correct"] += 1
        else:
            statistics[source]["incorrect"] += 1
            overall_statistics["incorrect"] += 1
        overall_statistics["total"] += 1

    for source in statistics:
        if statistics[source]["total"] > 0:
            statistics[source]["accuracy"] = statistics[source]["correct"] / statistics[source]["total"]
        else:
            statistics[source]["accuracy"] = 0.0

    if overall_statistics["total"] > 0:
        overall_statistics["accuracy"] = overall_statistics["correct"] / overall_statistics["total"]
    else:
        overall_statistics["accuracy"] = 0.0

    print("Overall statistics:")
    pprint(overall_statistics)
    print("-" * 50)
    print("By source:")
    pprint(statistics)


def run_benchmark(
    benchmark_name: str,
    agent_kwargs: Dict,
    max_workers: int = 1,
    sample_num: Optional[int] = None
):
    """Run evaluation on a benchmark."""
    save_path = f"results/{benchmark_name}_{agent_kwargs.get('save_path_suffix', 'default')}.jsonl"
    data_path = f"benchmark/{benchmark_name}.jsonl"

    assert os.path.exists(data_path), f"Data path {data_path} does not exist"

    os.makedirs("results", exist_ok=True)
    processed_data_id = get_processed_data_id(save_path)
    with open(data_path, "r", encoding="utf-8") as f:
        data_list = [json.loads(line) for line in f]
    data_list = [data for data in data_list if data["id"] not in processed_data_id]
    print(f"Processing {len(data_list)} tasks for {benchmark_name}...")

    process_batch(agent_kwargs, data_list, save_path, max_workers=max_workers)
    calculate_statistics(save_path, sample_num=sample_num)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Batch evaluate agents on benchmarks")
    parser.add_argument("--benchmark_name", type=str, required=True, help="Benchmark name (e.g., xbench_ds)")
    parser.add_argument("--max_workers", type=int, default=8, help="Max worker threads")
    parser.add_argument("--sample_num", type=int, default=None, help="Optional sample limit")
    
    # VLLM params
    parser.add_argument("--vllm_server_ip", type=str, default="127.0.0.1", help="VLLM server IP")
    parser.add_argument("--vllm_server_ports", type=str, default="8010", help="Comma-separated list of VLLM server ports")
    parser.add_argument("--vllm_model_name", type=str, required=True, help="VLLM model name")
    
    # Agent params
    parser.add_argument("--save_path_suffix", type=str, default="test", help="Suffix for save path")
    parser.add_argument("--tokenizer_path", type=str, default=None, help="Path to tokenizer")
    parser.add_argument("--max_context_length", type=int, default=262144, help="Max context length")
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Parse server ports
    server_ports = [int(p.strip()) for p in args.vllm_server_ports.split(",")]
    
    # Warn if multiple ports are specified
    if len(server_ports) > 1:
        logger.info(f"Using {len(server_ports)} VLLM server instances for load balancing: {server_ports}")
        logger.info("Make sure all specified ports have running VLLM servers.")
    else:
        logger.info(f"Using single VLLM server instance on port {server_ports[0]}")

    agent_kwargs = {
        "vllm_server_ip": args.vllm_server_ip,
        "vllm_server_ports": server_ports,
        "vllm_model_name": args.vllm_model_name,
        "save_path_suffix": args.save_path_suffix,
        "tokenizer_path": args.tokenizer_path,
        "max_context_length": args.max_context_length,
    }

    run_benchmark(
        args.benchmark_name,
        agent_kwargs,
        max_workers=args.max_workers,
        sample_num=args.sample_num
    )


if __name__ == "__main__":
    main()

