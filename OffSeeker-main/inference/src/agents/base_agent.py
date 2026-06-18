"""
Abstract Base Class for Search Agents
Defines the interface and common functionality for all search agents
"""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from loguru import logger
from copy import deepcopy
from transformers import AutoTokenizer
import json

from tools.tool_processor import ToolProcessor


class BaseSearchAgent(ABC):
    """
    Abstract base class for search agents with tool call support.
    
    This class defines the common interface and functionality that all search agents
    must implement, including tool call processing and conversation flow control.
    """
    
    def __init__(self,
                 system_prompt: str = "You are a helpful search agent.",
                 temperature: float = 0.6,
                 enable_hint: bool = False,
                 max_turns: int = 100,
                 tokenizer_path: Optional[str] = None,
                 max_context_length: int = 80000):
        """
        Initialize the base search agent.
        
        Args:
            system_prompt: System prompt for the agent
            temperature: Temperature for model generation
            enable_hint: Whether to enable additional hints
            max_turns: Maximum number of conversation turns
            tokenizer_path: Path to tokenizer for token counting
            max_context_length: Max context length to avoid context overflow
        """
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.enable_hint = enable_hint
        self.max_turns = max_turns
        self.tokenizer = None
        if tokenizer_path:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
            logger.info(f"Initialized tokenizer from {tokenizer_path}")
        self.max_context_length = max_context_length

        self.context_token_count = 0
        self.all_token_count = 0

        # Initialize tool call processor
        self.tool_processor = ToolProcessor()
        
        # Initialize conversation context and trajectory
        self.context = [{"role": "system", "content": self._get_system_prompt()}]
        self.context_token_count = self._count_token_count(self.context[0]["content"])
        self.all_token_count = self.context_token_count

        # Separate context (current session) and trajectory (all sessions)
        self.trajectory = []  # List[List[Dict]] - stores complete session histories
        
    def _get_system_prompt(self) -> str:
        """
        Get system prompt based on hint mode.
        
        Returns:
            System prompt string
        """
        if self.enable_hint:
            return self.system_prompt + self._get_hint_text()
        else:
            return self.system_prompt

    
    def _get_hint_text(self) -> str:
        """Get hint text for hint-enabled mode."""
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
    
    @abstractmethod
    def _call_model(self, messages: List[Dict], **kwargs) -> str:
        """
        Abstract method to call the underlying model.
        
        This method must be implemented by concrete agent classes to handle
        the specific model calling logic (VLLM, API, etc.).
        
        Args:
            messages: List of conversation messages
            **kwargs: Additional model-specific parameters
            
        Returns:
            Model response as string
        """
        pass
    

    def _count_token_count(self, text: str) -> int:
        """
        Count token count of the text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Token count
        """
        if not isinstance(text, str):
            text = str(text)

        return len(self.tokenizer.encode(text)) if self.tokenizer else 0

    
    def _chat_completion(self, messages: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
        """
        Unified chat completion method with stop token handling.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Tuple of (response_text, stop_reason)
        """
        max_trials = 5

        raw_messages = deepcopy(messages)
        error_prompt = ""

        for trial in range(max_trials):
            try:
                new_messages = deepcopy(raw_messages)
                new_messages[-1]["content"] += error_prompt
                raw_text = self._call_model(new_messages)
                
                if raw_text is None:
                    return None, None
                
                # Handle stop tokens
                enclosed_tags = re.findall(r"</?[^>]+>", raw_text)
                # Only count reasoning and tool_call
                valid_tags = ["<think>", "</think>", "<tool_call>", "</tool_call>", "<answer>", "</answer>"]
                enclosed_tags = [tag for tag in enclosed_tags if tag in valid_tags]
                assert len(enclosed_tags) >= 3

                if len(enclosed_tags) == 3:
                    last_enclosed_tag = enclosed_tags[2]
                    assert last_enclosed_tag in ["<tool_call>", "<answer>"]
                    if last_enclosed_tag == "<tool_call>":
                        raw_text += "</tool_call>"
                        stop_reason = "</tool_call>"
                    elif last_enclosed_tag == "<answer>":
                        raw_text += "</answer>"
                        stop_reason = "</answer>"
                    return raw_text, stop_reason

                else:
                    last_enclosed_tag = enclosed_tags[3]
                    
                    stop_reason = None

                    assert last_enclosed_tag in ["</tool_call>", "</answer>"]
                    stop_reason = last_enclosed_tag
                    raw_text = raw_text.split(last_enclosed_tag)[0] + last_enclosed_tag

                    # Check if tool call format is correct (can be parsed as JSON)
                    if "</tool_call>" in raw_text:
                        tool_call_text = deepcopy(raw_text)
                        tool_call_text = tool_call_text.split("<tool_call>")[1].split("</tool_call>")[0].strip()
                        try:
                            tool_call = json.loads(tool_call_text)
                        except Exception as e:
                            continue

                    return raw_text, stop_reason
            
            except AssertionError as e:
                import traceback
                traceback.print_exc()
                print(f"Assertion Error. Raw model response: {raw_text}")
                error_prompt = "Your response is not valid. You should always output the thinking process before the tool call and the answer, which has already shown in previous text. Your thinking should be enclosed by <think> </think> tags, and the tool call should be enclosed by <tool_call> </tool_call> tags, and the answer should be enclosed by <answer> </answer> tags."
                continue
        
            except Exception as e:
                import traceback
                traceback.print_exc()
                continue
        
        logger.error(f"Chat completion failed after {max_trials} trials.")
        return "Chat completion failed.", None

    
    def chat_step(self, prompt: str) -> str:
        """
        Single conversation step.
        
        Args:
            prompt: User prompt
            
        Returns:
            Agent response
        """
        self.context.append({"role": "user", "content": prompt})

        response, stop_reason = self._chat_completion(self.context)
        self.context.append({"role": "assistant", "content": response})
        
        return response
    
    def action_step(self, response: str) -> Optional[str]:
        """
        Process tool calls from agent response.
        
        Args:
            response: Agent response containing potential tool calls
            
        Returns:
            Tool execution results or None
        """
        # Extract tool calls
        tool_calls = self.tool_processor.extract_tool_calls(response)
        
        if not tool_calls:
            return None
        
        # Execute tool calls
        results = self.tool_processor.execute_tool_calls(tool_calls)
        
        # Format response
        tool_response = self.tool_processor.format_tool_response(tool_calls, results)
        
        return tool_response
    
    def run_loop(self, prompt: str) -> str:
        """
        Main execution loop with session restart capability.
        
        Args:
            prompt: Initial user prompt
            
        Returns:
            Final answer or error message
        """
        self.reset()
        
        user_prompt = prompt
        turn_idx = 0

        while turn_idx < self.max_turns:
            logger.debug(f"Current turn: {turn_idx + 1}")
            logger.info(f"Current context token count: {self.context_token_count}")

            response = self.chat_step(user_prompt)
            if response is None:
                return "Failed to solve the task because of chat completion failed."
            response_token_count = self._count_token_count(response)
            self.all_token_count += response_token_count
            self.context_token_count += response_token_count

            # Check if token limit is reached
            if self.context_token_count > self.max_context_length:
                logger.warning(f"Context token limit reached: {self.context_token_count}")
                # Save current session to trajectory and start new session
                self._save_session_to_trajectory()

                return "Failed to solve the task because of context token limit."

            logger.info(f"Model Response: {response}")

            # Check for tool calls
            tool_calls = self.tool_processor.extract_tool_calls(response)
            if tool_calls:
                # Execute tool calls
                tool_response = self.action_step(response)
                logger.debug(f"Tool Response: {tool_response}")
                if tool_response:
                    user_prompt = f"{tool_response}\n\nPlease continue to solve the task."
            else:
                # Check for final answer
                answer = self._extract_answer(response)
                if answer:
                    self._save_session_to_trajectory()
                    return answer
                else:
                    user_prompt = f"The environment did not provide any feedback. If you have output the tool call, please check whether your tool call is correct, and try again."

            turn_idx += 1
            
            # Check token count for user prompt
            env_token_count = self._count_token_count(user_prompt)
            self.context_token_count += env_token_count
            self.all_token_count += env_token_count
            if self.context_token_count > self.max_context_length:
                logger.warning(f"Context token limit reached: {self.context_token_count}")
                # Save current session to trajectory and start new session
                self._save_session_to_trajectory()
                return "Failed to solve the task because of context token limit."

        # If we completed all turns without finding an answer, continue to next iteration
        if turn_idx >= self.max_turns:
            return "Failed to solve the task because of turn limit."

    
    def _save_session_to_trajectory(self):
        """Save current session context to trajectory."""
        if self.context:
            self.trajectory.append(deepcopy(self.context))
            logger.info(f"Saved session to trajectory. Total sessions: {len(self.trajectory)}")
    
    def reset(self):
        """Reset conversation context."""
        self._start_new_session()
    
    def get_context(self) -> List[Dict]:
        """Get current conversation context."""
        return self.context

    def _extract_answer(self, response: str) -> Optional[str]:
        """Extract final answer from response."""
        answer_pattern = r'<answer>(.*?)</answer>'
        match = re.search(answer_pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information - to be implemented by subclasses."""
        return {"type": "base", "class": self.__class__.__name__}
    
    def health_check(self) -> bool:
        """Check if the agent is healthy - to be implemented by subclasses."""
        return True

