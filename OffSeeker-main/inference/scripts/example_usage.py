"""
Example usage of OffSeeker
Demonstrates how to use the VLLMSearchAgent for deep research tasks
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path for direct imports
SCRIPT_DIR = Path(__file__).parent.parent.absolute()
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agents.vllm_agent import VLLMSearchAgent
from tools import ALL_TOOL_SCHEMAS
import json

def main():
    # Configuration
    server_ip = os.getenv("VLLM_SERVER_IP", "127.0.0.1")
    server_ports = [int(p) for p in os.getenv("VLLM_SERVER_PORTS", "8010").split(",")]
    model_name = os.getenv("VLLM_MODEL_NAME", "your_model_name")
    tokenizer_path = os.getenv("TOKENIZER_PATH", None)
    max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "262144"))
    
    # Build tool schemas for system prompt
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
    
    # Create agent
    agent = VLLMSearchAgent(
        server_ip=server_ip,
        server_port=server_ports,
        model_name=model_name,
        system_prompt=system_prompt,
        enable_hint=True,
        tokenizer_path=tokenizer_path,
        max_context_length=max_context_length,
    )
    
    # Example task
    task = "What is the capital of France?"
    
    print(f"Task: {task}")
    print("Running agent...")
    print("-" * 50)
    
    # Run the agent
    response = agent.run_loop(task)
    
    print("-" * 50)
    print(f"Final Answer: {response}")
    print(f"Total tokens used: {agent.all_token_count}")
    print(f"Number of turns: {len(agent.trajectory)}")

if __name__ == "__main__":
    main()

