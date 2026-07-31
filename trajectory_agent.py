"""
Trajectory Recording Agent
Uses OpenAI-style API for model calls and records complete agent trajectories
for distillation to smaller models.

This agent maintains full compatibility with OffSeeker's prompt and tool definitions.
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

# Add OffSeeker-main to path for imports
import sys
offseeker_path = os.path.join(os.path.dirname(__file__), 'OffSeeker-main')
offseeker_src_path = os.path.join(offseeker_path, 'inference/src')
if offseeker_src_path not in sys.path:
    sys.path.insert(0, offseeker_src_path)

from tools.tool_processor import ToolProcessor
from deepseek_thinking_compat import assistant_message_to_dict, build_chat_completion_kwargs, resolve_effective_model


class TrajectoryRecordingAgent:
    """
    Agent that uses OpenAI-style API for model calls and records complete trajectories.

    This agent:
    1. Uses OpenAI-style chat.completions API (compatible with many providers)
    2. Records complete conversation history with tool calls and results
    3. Saves trajectory to JSON file for downstream distillation
    4. Maintains full compatibility with OffSeeker's prompt and tool definitions

    The trajectory format follows OpenAI's messages format:
    [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "...", "tool_calls": [...]},
      {"role": "tool", "tool_call_id": "...", "content": "..."},
      ...
    ]
    """

    # Default system prompt (same as OffSeeker)
    DEFAULT_SYSTEM_PROMPT = "You are a helpful search agent."

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        system_prompt: str = None,
        temperature: float = 0.6,
        enable_hint: bool = False,
        max_turns: Optional[int] = None,
        hard_safety_turns: int = 200,
        log_dir: str = "logs/trajectories",
        # Context compression configuration
        max_context_tokens: int = 100000,
        keep_recent_messages: int = 12,
        max_tool_result_chars: int = 3000,
        max_assistant_chars: int = 1500,
        tokenizer_path: Optional[str] = None,
        # Parallel tool execution configuration
        max_tool_workers: int = 4,
        enable_parallel_tools: bool = True,
    ):
        """
        Initialize the trajectory recording agent.

        Args:
            api_base: Base URL for the API (e.g., "https://api.openai.com/v1")
            api_key: API key for authentication
            model_id: Model identifier (e.g., "gpt-4", "deepseek-chat")
            system_prompt: System prompt for the agent
            temperature: Temperature for sampling
            enable_hint: Whether to enable additional hints (same as OffSeeker)
            max_turns: Optional soft turn limit. None means no intentional limit.
            hard_safety_turns: High safety cap to prevent infinite loops
            log_dir: Directory to save trajectory logs
        """
        self.api_base = api_base
        self.api_key = api_key
        self.model_id = model_id
        self.effective_model_id = resolve_effective_model(model_id)
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.temperature = temperature
        self.enable_hint = enable_hint
        self.max_turns = max_turns
        self.hard_safety_turns = hard_safety_turns
        self.log_dir = log_dir

        # Context compression configuration
        self.max_context_tokens = max_context_tokens
        self.keep_recent_messages = keep_recent_messages
        self.max_tool_result_chars = max_tool_result_chars
        self.max_assistant_chars = max_assistant_chars
        self.tokenizer = None
        if tokenizer_path:
            try:
                from transformers import AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)
                logger.info(f"Loaded tokenizer from {tokenizer_path} for context compression")
            except Exception as e:
                logger.warning(f"Failed to load tokenizer from {tokenizer_path}: {e}. Using char-based token estimate.")

        # Parallel tool execution configuration
        self.max_tool_workers = max_tool_workers
        self.enable_parallel_tools = enable_parallel_tools

        # Build tool schemas string for system prompt
        self.tool_schemas_str = "\n".join([
            json.dumps(schema, ensure_ascii=False, indent=2)
            for schema in self._get_tool_schemas()
        ])

        # Initialize OpenAI client
        from openai import OpenAI
        self.client = OpenAI(
            base_url=api_base,
            api_key=api_key,
        )

        # Tool processor for handling tool calls (same as OffSeeker)
        self.tool_processor = ToolProcessor()

        # Get tool schemas for API (same as OffSeeker)
        self.tool_schemas = self._get_tool_schemas()

        # Initialize messages list (OpenAI format)
        self.messages: List[Dict] = []

        # Task and metadata for trajectory recording
        self.current_task: Optional[str] = None
        self.trajectory_metadata: Dict[str, Any] = {}

        logger.info(
            f"Initialized TrajectoryRecordingAgent with model: {model_id}, "
            f"enable_hint: {enable_hint}, max_turns: {max_turns}, hard_safety_turns: {hard_safety_turns}"
        )

    def _get_system_prompt(self) -> str:
        """
        Get system prompt based on hint mode (same as OffSeeker).

        Returns:
            System prompt string with <answer> tag instructions
        """
        # OffSeeker-style prompt with <answer> tag instructions
        base_prompt = f"""
You are a helpful search agent that should solve difficult web-search tasks by iteratively gathering evidence.

Your response must follow this protocol:

1. If you are still investigating, you may briefly explain your reasoning inside <think>...</think> tags and then use tool calls.
2. If you have finished the task, output exactly one <answer>...</answer> block with the final answer only.
3. When you output <answer>...</answer>, do not make any tool calls in the same response.

Important behavior rules:
- Be rigorous and evidence-driven.
- Treat every condition in the question as binding.
- Prefer primary or close-to-primary sources when possible.
- Use search broadly at first, then use visit_urls to verify promising pages deeply.
- If search results are noisy, reformulate and keep investigating instead of guessing.
- Do not output <answer> unless you believe the answer is sufficiently supported.
- If you are uncertain, continue gathering evidence rather than fabricating a conclusion.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{self.tool_schemas_str}
</tools>

For each function call, use the function calling interface with the function name and arguments.
"""

        if self.enable_hint:
            return base_prompt + "\n" + self._get_hint_text()
        else:
            return base_prompt

    def _get_hint_text(self) -> str:
        """Get hint text for hint-enabled mode (same as OffSeeker)."""
        return """
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

    def _extract_answer(self, response_content: str) -> Optional[str]:
        """
        Extract final answer from response using <answer> tags (same as OffSeeker).

        Args:
            response_content: The response content from the model

        Returns:
            Extracted answer if found, None otherwise
        """
        text = response_content or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
        matches = re.findall(r"<answer>(.*?)</answer>", text, re.DOTALL | re.IGNORECASE)
        if not matches:
            return None
        return matches[-1].strip()

    def _count_tokens(self, text: str) -> int:
        """Estimate token count; uses tokenizer if available, else ~4 chars/token heuristic."""
        if not isinstance(text, str):
            text = str(text)
        if self.tokenizer is not None:
            try:
                return len(self.tokenizer.encode(text))
            except Exception:
                pass
        return max(1, len(text) // 4)

    def _count_tokens_messages(self, messages: List[Dict]) -> int:
        """Estimate total token count for a list of messages."""
        total = 0
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                total += self._count_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        total += self._count_tokens(part["text"])
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    total += self._count_tokens(fn.get("name", ""))
                    total += self._count_tokens(fn.get("arguments", ""))
        return total

    def _build_llm_context(self) -> List[Dict]:
        """
        Build the message list sent to the LLM.

        self.messages always stores the FULL trajectory (saved for distillation).
        When it approaches max_context_tokens, return a compressed VIEW that truncates
        older tool results / assistant content while keeping the recent window and all
        tool_call/tool pairings intact (so the API stays valid). The full trajectory
        is never mutated by compression.
        """
        if len(self.messages) <= 2:
            return self.messages

        total_tokens = self._count_tokens_messages(self.messages)
        if total_tokens <= self.max_context_tokens:
            return self.messages

        compressed = list(self.messages[:2])  # system + task, always intact
        body = self.messages[2:]
        keep = min(self.keep_recent_messages, len(body))
        split = len(body) - keep
        old_body = body[:split]
        recent_body = body[split:]

        for msg in old_body:
            role = msg.get("role")
            content = msg.get("content")
            limit = self.max_tool_result_chars if role == "tool" else self.max_assistant_chars
            if isinstance(content, str) and len(content) > limit:
                new_msg = dict(msg)
                new_msg["content"] = (
                    content[:limit]
                    + f"\n...[truncated {len(content) - limit} chars for context management]..."
                )
                compressed.append(new_msg)
                continue
            compressed.append(msg)

        compressed.extend(recent_body)

        new_total = self._count_tokens_messages(compressed)
        logger.info(
            f"Context compressed: {total_tokens} -> {new_total} tokens "
            f"(kept last {keep} messages intact)"
        )
        self.trajectory_metadata.setdefault("context_compressions", []).append(
            {"turn_messages": len(self.messages), "before": total_tokens, "after": new_total}
        )
        return compressed

    def _execute_tool_call(self, item) -> Dict[str, str]:
        """
        Execute a single parsed tool call. Used for both serial and parallel execution.

        Never raises: all exceptions are caught and returned as error strings so one
        tool failure never collapses the whole batch.
        """
        tool_call, func_name, arguments = item
        logger.info(f"Executing tool: {func_name} with args: {arguments}")
        try:
            result = self.tool_processor.tools[func_name](arguments)
            logger.info(f"Tool {func_name} completed successfully")
        except Exception as e:
            result = f"Error executing {func_name}: {str(e)}"
            logger.error(result)
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": func_name,
            "content": str(result),
        }

    def _get_tool_schemas(self) -> List[Dict]:
        """Get tool schemas in OpenAI format (same as OffSeeker)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web for information using Google search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of search query strings"
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_wiki",
                    "description": "Search Wikipedia for information about entities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of entity names to search"
                            }
                        },
                        "required": ["entities"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "visit_urls",
                    "description": "Visit URLs and return webpage content or query-focused reports",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "urls": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of URLs to visit"
                            },
                            "query": {
                                "type": "string",
                                "description": "Optional search question to focus the visit"
                            },
                        },
                        "required": ["urls"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_code",
                    "description": "Execute Python code",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute"
                            }
                        },
                        "required": ["code"],
                    },
                },
            },
        ]

    def run_with_trajectory(
        self,
        task: str,
        save_trajectory: bool = True,
        trajectory_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the agent and record complete trajectory.

        Args:
            task: The task to perform
            save_trajectory: Whether to save trajectory to file
            trajectory_path: Custom path for trajectory file

        Returns:
            Dictionary containing:
                - answer: Final answer
                - trajectory: Complete message history
                - metadata: Execution metadata
        """
        # Initialize messages with system prompt
        self.messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ]

        # Add task as first user message
        self.messages.append({"role": "user", "content": task})

        # Initialize metadata
        self.trajectory_metadata = {
            "task": task,
            "model": self.effective_model_id,
            "api_base": self.api_base,
            "started_at": datetime.now().isoformat(),
            "temperature": self.temperature,
            "enable_hint": self.enable_hint,
            "max_turns": self.max_turns,
            "hard_safety_turns": self.hard_safety_turns,
        }

        logger.info(f"Starting task: {task[:100]}...")

        # Main conversation loop
        turn = 0
        while True:
            if self.max_turns is not None and turn >= self.max_turns:
                self.trajectory_metadata["finished_at"] = datetime.now().isoformat()
                self.trajectory_metadata["status"] = "max_turns_reached"
                self.trajectory_metadata["turns"] = turn
                logger.warning("Soft max turns reached without completion")
                if save_trajectory:
                    self._save_trajectory(trajectory_path)
                return {
                    "answer": None,
                    "trajectory": self._serialize_messages(),
                    "metadata": self.trajectory_metadata,
                }
            if turn >= self.hard_safety_turns:
                self.trajectory_metadata["finished_at"] = datetime.now().isoformat()
                self.trajectory_metadata["status"] = "hard_safety_turns_reached"
                self.trajectory_metadata["turns"] = turn
                logger.warning("Hard safety turns reached without completion")
                if save_trajectory:
                    self._save_trajectory(trajectory_path)
                return {
                    "answer": None,
                    "trajectory": self._serialize_messages(),
                    "metadata": self.trajectory_metadata,
                }

            turn += 1
            logger.info(f"Turn {turn}{'' if self.max_turns is None else f'/{self.max_turns}'}")

            # Call model
            try:
                completion = self.client.chat.completions.create(
                    **build_chat_completion_kwargs(
                        model_id=self.model_id,
                        messages=self._build_llm_context(),
                        tools=self.tool_schemas,
                        temperature=self.temperature,
                    )
                )

                response_message = completion.choices[0].message

                # Append assistant message to trajectory
                self.messages.append(assistant_message_to_dict(response_message))

                # Check for <answer> tag in content (OffSeeker-style stopping)
                answer = self._extract_answer(response_message.content or "")
                if answer:
                    # Found final answer in <answer> tags
                    self.trajectory_metadata["finished_at"] = datetime.now().isoformat()
                    self.trajectory_metadata["status"] = "completed"
                    self.trajectory_metadata["turns"] = turn

                    logger.info(f"Task completed in {turn} turns (found <answer> tag)")

                    # Save trajectory if requested
                    if save_trajectory:
                        self._save_trajectory(trajectory_path)

                    return {
                        "answer": answer,
                        "trajectory": self._serialize_messages(),
                        "metadata": self.trajectory_metadata,
                    }

                # Check for tool calls
                if not response_message.tool_calls:
                    # No tool calls and no <answer> tag - treat as best-effort natural language completion
                    content = response_message.content or ""
                    self.trajectory_metadata["finished_at"] = datetime.now().isoformat()
                    self.trajectory_metadata["status"] = "completed_no_tool_calls"
                    self.trajectory_metadata["turns"] = turn
                    self.trajectory_metadata["note"] = "No tool calls or <answer> tag, using full content as best-effort answer"

                    logger.info(f"Task completed in {turn} turns (no tool calls)")

                    # Save trajectory if requested
                    if save_trajectory:
                        self._save_trajectory(trajectory_path)

                    return {
                        "answer": content,
                        "trajectory": self._serialize_messages(),
                        "metadata": self.trajectory_metadata,
                    }

                # Process tool calls: parse all first (fail-fast on bad JSON),
                # then execute valid calls in parallel for lower latency.
                tool_parse_error = None
                parsed_calls = []
                for tool_call in response_message.tool_calls:
                    func_name = tool_call.function.name
                    arguments_str = tool_call.function.arguments
                    try:
                        arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                        parsed_calls.append((tool_call, func_name, arguments))
                    except json.JSONDecodeError as e:
                        tool_parse_error = (
                            f"Error: Your tool call for '{func_name}' has invalid JSON format in arguments. "
                            f"Please ensure your arguments are properly formatted JSON. "
                            f"Error details: {str(e)}"
                        )
                        logger.error(f"Tool call JSON parse error: {tool_parse_error}")
                        break

                if tool_parse_error:
                    self.messages.append({"role": "user", "content": tool_parse_error})
                    self.trajectory_metadata["last_error"] = tool_parse_error
                    if save_trajectory:
                        self._save_trajectory(trajectory_path)
                    continue

                if self.enable_parallel_tools and len(parsed_calls) > 1:
                    workers = min(self.max_tool_workers, len(parsed_calls))
                    with ThreadPoolExecutor(max_workers=workers) as ex:
                        tool_responses = list(ex.map(self._execute_tool_call, parsed_calls))
                else:
                    tool_responses = [self._execute_tool_call(c) for c in parsed_calls]

                self.messages.extend(tool_responses)

            except Exception as e:
                logger.error(f"Error in turn {turn}: {e}")
                self.trajectory_metadata["error"] = str(e)
                self.trajectory_metadata["finished_at"] = datetime.now().isoformat()
                self.trajectory_metadata["turns"] = turn
                if self._is_context_limit_error(e):
                    self.trajectory_metadata["status"] = "context_limit_reached"
                else:
                    self.trajectory_metadata["status"] = "error"

                if save_trajectory:
                    self._save_trajectory(trajectory_path)

                return {
                    "answer": None,
                    "trajectory": self._serialize_messages(),
                    "metadata": self.trajectory_metadata,
                }

    def _is_context_limit_error(self, error: Exception) -> bool:
        text = str(error).lower()
        markers = [
            "maximum context length",
            "context length",
            "context_window_exceeded",
            "too many tokens",
            "prompt is too long",
            "context limit",
            "reached token limit",
        ]
        return any(marker in text for marker in markers)

    def _serialize_messages(self) -> List[Dict]:
        """Serialize messages to JSON-serializable format."""
        serialized = []
        for msg in self.messages:
            if isinstance(msg, dict):
                serialized.append(msg)
            elif hasattr(msg, "model_dump"):
                # OpenAI SDK ChatCompletionMessage
                d = msg.model_dump(exclude_none=True)
                # Preserve reasoning_content if present (for o1-style models)
                if hasattr(msg, "reasoning_content") and msg.reasoning_content:
                    d["reasoning_content"] = msg.reasoning_content
                serialized.append(d)
        return serialized

    def _save_trajectory(self, custom_path: Optional[str] = None):
        """Save trajectory to file."""
        if custom_path:
            path = Path(custom_path)
        else:
            # Create path based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = self.model_id.replace("/", "_").replace(":", "_")
            path = Path(self.log_dir) / model_name / f"task_{timestamp}.json"

        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare trajectory data
        trajectory_data = {
            "metadata": self.trajectory_metadata,
            "messages": self._serialize_messages(),
        }

        # Write to file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trajectory_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved trajectory to: {path}")


def main():
    """Example usage of TrajectoryRecordingAgent."""
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    api_base = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or os.getenv("API_BASE")
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    model_id = os.getenv("MODEL_NAME") or os.getenv("MODEL_ID", "gpt-4o")

    if not api_base or not api_key:
        logger.error("Please set OPENAI_API_BASE and OPENAI_API_KEY in .env file")
        return

    # Create agent with hint enabled (same as OffSeeker)
    agent = TrajectoryRecordingAgent(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        temperature=0.6,
        enable_hint=True,  # Enable detailed hints
        max_turns=20,
    )

    # Run a task
    task = "What is the capital of France? Tell me about its population and famous landmarks."
    result = agent.run_with_trajectory(task, save_trajectory=True)

    print("\n" + "=" * 50)
    print("FINAL ANSWER:")
    print("=" * 50)
    print(result["answer"])
    print("\n" + "=" * 50)
    print(f"METADATA: {result['metadata']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
