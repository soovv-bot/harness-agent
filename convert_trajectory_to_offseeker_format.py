"""
Trajectory Format Converter
Converts OpenAI-style trajectories (from trajectory_agent.py) to OffSeeker format for training.

This script converts trajectories recorded using OpenAI's native function calling
into the text-based format used by OffSeeker for training small models.

Usage:
    python convert_trajectory_to_offseeker_format.py \
        --input logs/trajectories/deepseek-chat \
        --output logs/offseeker_format \
        --enable_hint
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
from copy import deepcopy
from tqdm import tqdm

# Add OffSeeker-main to path for imports
offseeker_path = os.path.join(os.path.dirname(__file__), 'OffSeeker-main')
if offseeker_path not in sys.path:
    sys.path.insert(0, offseeker_path)

from inference.src.tools import ALL_TOOL_SCHEMAS


# OffSeeker system prompt template (from evaluate.py and example_usage.py)
OFFSEEKER_SYSTEM_PROMPT_TEMPLATE = """
You are a helpful agent that can appropriately leverage the available tools to solve complex tasks.
Your response should strictly follow the format:

1. Provide an explanation for your action, which should be enclosed by <think> </think> tags.
First, review the previous steps to provide context.
Next, describe any new observations or relevant information obtained since the last step.
Finally, clearly explain your reasoning and the rationale behind your current output or decision.

2. Use the available tools to gather information or perform actions.
Tool calls should be wrapped in <function_call> </function_call> tags and follow the JSON format.
Then, we will extract tool call, provide tool response for you. The tool response will be enclosed by <result> </result> tags.

3. If you have finished the task, provide the final answer. The final answer should be enclosed by <answer> </answer> tags.
In that case, you should not output any more tool calls.

You should always dive deep into the webpage content to confirm some details.
You can flexibly use multiple search terms or URLs at once to speed up the process and enhance the breadth of your search.
Besides the given tools, you can also use multiple tool calls in sequence to solve the task comprehensively.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_schemas}
</tools>

For each function call, return a json object with function name and arguments within <function_call> </function_call> XML tags:
<function_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</function_call>
"""

# Hint text from OffSeeker (same as base_agent.py)
HINT_TEXT = """
<hint>
You must strictly follow the following principles when performing search-based reasoning and information gathering:

1. **Accuracy and Verification First.**
   - Never make conclusions without ample, verified information.
   - Each condition mentioned in the question is absolutely correct and must be fully satisfied.
   - Always validate every constraint (e.g., version numbers, dates, names, locations) explicitly — never assume or generalize.
   - If any information is missing or uncertain, continue searching and verifying until the evidence is complete.

2. **Precision in Data Collection and Preprocessing.**
   - The accuracy of the first step (data gathering and filtering) determines the success of the entire reasoning chain.
   - Incorrect or noisy initial data will mislead all subsequent reasoning, even if later logic is flawless.
   - Carefully check for inclusion/exclusion conditions (e.g., filtering "acting ministers"), and ensure the dataset aligns exactly with the problem definition.

3. **Critical and Adaptive Thinking.**
   - Do not blindly trust tool outputs or single information sources.
   - When encountering conflicting or surprising evidence, pause, question, and investigate before proceeding.
   - Be ready to update or discard your current hypothesis when new evidence contradicts it — avoid cognitive inertia.
   - Handle apparent contradictions by cross-verifying details across multiple credible sources.

4. **Strategic Search Planning.**
   - Treat the problem like a detective case: start broad, gather clues, then progressively narrow the focus.
   - For vague or multi-faceted problems, design multiple parallel search queries with focused keyword subsets rather than one overly complex query.
   - Some steps can be processed concurrently; explore parallel queries to accelerate information collection.

5. **Evaluation and Error Correction.**
   - Continuously check whether your intermediate findings remain consistent with the original task.
   - When realizing a possible early-stage mistake (e.g., wrong entity set), stop and reinitialize the search with corrected parameters.
   - The ability to detect and correct errors early is as important as choosing the right initial approach.

6. **Judicious Use of Search Engines and Language Context.**
   - Use the search language appropriately: English queries for global content, Chinese queries (or add "site:baidu.com") for Chinese-specific information.
   - Avoid depending solely on Google snippets — dive into full webpages and primary sources such as Wikipedia or Baidu Encyclopedia for comprehensive data.

7. **Breadth and Depth Balance.**
   - If the search results are insufficient, broaden your criteria and simplify your queries. Then, fastly verify all listed entities against all constraints. If any entity does not meet the constraints, fastly update your hypothesis and try other entities.
   - Never overload a single search with too many constraints — collect partial clues from multiple searches and synthesize them.
   - Maybe it is hard to find the required entity. It is better to behave like: (1) search for relevant information about A B C D in parallel, (2) verified that A B C D do not meet the constraints, (3) try searching for other entities like E F G... until you find the required entity that can meet all constraints.
   - If several entities seem to match partially, methodically verify each one against all constraints before final selection.

8. **Output Discipline.**
   - Never output the final `<answer>...</answer>` unless you are absolutely sure the answer is correct and fully verified.
   - If you are still gathering or confirming information, do not output an answer and do not make tool calls simultaneously.

9. **Response Discipline.**
    - Always output the thinking process before the tool call and the answer, which has already shown in previous text.

**Summary Principle:**
A successful search agent is rigorous, skeptical, and adaptive — like an experienced investigator who continually verifies, refines, and corrects its reasoning path until the evidence perfectly fits all given constraints.
</hint>
"""


class TrajectoryConverter:
    """Convert OpenAI-style trajectories to OffSeeker format."""

    def __init__(self, enable_hint: bool = False):
        """
        Initialize the converter.

        Args:
            enable_hint: Whether to include hint text in system prompt
        """
        self.enable_hint = enable_hint

        # Prepare tool schemas string
        self.tool_schemas_str = "\n".join([
            json.dumps(schema, ensure_ascii=False, indent=2)
            for schema in ALL_TOOL_SCHEMAS
        ])

        # Build system prompt
        base_prompt = OFFSEEKER_SYSTEM_PROMPT_TEMPLATE.format(
            tool_schemas=self.tool_schemas_str
        )
        if enable_hint:
            self.system_prompt = base_prompt + "\n" + HINT_TEXT
        else:
            self.system_prompt = base_prompt

    def convert_trajectory(self, trajectory_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a single trajectory from OpenAI format to OffSeeker format.

        Args:
            trajectory_data: OpenAI-format trajectory with metadata and messages

        Returns:
            OffSeeker-format trajectory with conversations list
        """
        messages = trajectory_data.get("messages", [])
        metadata = trajectory_data.get("metadata", {})

        # Build conversations list in OffSeeker format
        conversations = []

        # Add system prompt
        conversations.append({
            "role": "system",
            "content": self.system_prompt
        })

        # Process messages
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg["role"] == "user":
                # User message - keep as is
                conversations.append({
                    "role": "user",
                    "content": msg["content"]
                })

            elif msg["role"] == "assistant":
                # Assistant message - may contain tool_calls
                assistant_content = msg.get("content", "")
                tool_calls = msg.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls - regular assistant response
                    conversations.append({
                        "role": "assistant",
                        "content": assistant_content
                    })
                else:
                    # Has tool calls - convert to OffSeeker format
                    assistant_parts = []

                    # Add thinking/content if present
                    if assistant_content:
                        assistant_parts.append(f"<think>{assistant_content}</think>")

                    # Convert tool calls to <function_call> format
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        arguments = tool_call["function"]["arguments"]
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)

                        function_call_json = json.dumps({
                            "name": func_name,
                            "arguments": arguments
                        }, ensure_ascii=False)

                        assistant_parts.append(
                            f"<function_call>\n{function_call_json}\n</function_call>"
                        )

                    conversations.append({
                        "role": "assistant",
                        "content": "\n".join(assistant_parts)
                    })

                    # Process tool results immediately after tool calls
                    tool_results = []
                    j = i + 1
                    while j < len(messages) and messages[j]["role"] == "tool":
                        tool_msg = messages[j]
                        tool_name = tool_msg.get("name", "")
                        tool_content = tool_msg.get("content", "")
                        tool_results.append(
                            f"Tool: {tool_name}\nResult: {tool_content}"
                        )
                        j += 1

                    if tool_results:
                        conversations.append({
                            "role": "user",
                            "content": "<result>\n" + "\n\n".join(tool_results) + "\n</result>"
                        })
                        i = j - 1  # Skip the tool messages we just processed

            elif msg["role"] == "tool":
                # Tool messages are processed together with assistant messages
                # Skip here to avoid duplicate processing
                pass

            i += 1

        # Build output format
        return {
            "task": metadata.get("task", ""),
            "model": metadata.get("model", ""),
            "started_at": metadata.get("started_at", ""),
            "finished_at": metadata.get("finished_at", ""),
            "status": metadata.get("status", ""),
            "turns": metadata.get("turns", 0),
            "enable_hint": self.enable_hint,
            "conversations": conversations
        }


def convert_file(input_path: str, output_path: str, enable_hint: bool = False):
    """Convert a single trajectory file."""
    converter = TrajectoryConverter(enable_hint=enable_hint)

    with open(input_path, "r", encoding="utf-8") as f:
        trajectory_data = json.load(f)

    converted = converter.convert_trajectory(trajectory_data)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)

    logger.info(f"Converted: {input_path} -> {output_path}")


def convert_directory(input_dir: str, output_dir: str, enable_hint: bool = False):
    """Convert all trajectory files in a directory."""
    converter = TrajectoryConverter(enable_hint=enable_hint)

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Find all JSON files
    json_files = list(input_path.rglob("*.json"))
    logger.info(f"Found {len(json_files)} trajectory files")

    converted_count = 0
    failed_count = 0

    for json_file in tqdm(json_files, desc="Converting trajectories"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                trajectory_data = json.load(f)

            converted = converter.convert_trajectory(trajectory_data)

            # Preserve directory structure
            relative_path = json_file.relative_to(input_path)
            output_file = output_path / relative_path
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)

            converted_count += 1

        except Exception as e:
            logger.error(f"Failed to convert {json_file}: {e}")
            failed_count += 1

    logger.info(f"Conversion complete: {converted_count} succeeded, {failed_count} failed")


def main():
    parser = argparse.ArgumentParser(
        description="Convert OpenAI-style trajectories to OffSeeker format"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input trajectory file or directory"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file or directory"
    )
    parser.add_argument(
        "--enable-hint",
        action="store_true",
        help="Include hint text in system prompt"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if input_path.is_file():
        convert_file(str(input_path), str(output_path), args.enable_hint)
    elif input_path.is_dir():
        convert_directory(str(input_path), str(output_path), args.enable_hint)
    else:
        logger.error(f"Input path not found: {args.input}")


if __name__ == "__main__":
    main()
