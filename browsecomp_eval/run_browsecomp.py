"""
BrowseComp Evaluation Script for OffSeeker-trained Models

Workflow:
1. Load BrowseComp dataset
2. Use TrajectoryRecordingAgent to run each task
3. Extract answer from <answer>...</answer> tags
4. Use LLM grader to judge if the answer is correct
"""

import os
import re
import json
import base64
import hashlib
import random
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, List
from loguru import logger
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Import from local modules
from eval_types import SamplerBase, SamplerResponse, MessageList
import common
from trajectory_agent import TrajectoryRecordingAgent


def derive_key(password: str, length: int) -> bytes:
    """Derive a fixed-length key from the password using SHA256."""
    hasher = hashlib.sha256()
    hasher.update(password.encode())
    key = hasher.digest()
    return key * (length // len(key)) + key[: length % len(key)]


def decrypt(ciphertext_b64: str, password: str) -> str:
    """Decrypt base64-encoded ciphertext with XOR."""
    encrypted = base64.b64decode(ciphertext_b64)
    key = derive_key(password, len(encrypted))
    decrypted = bytes(a ^ b for a, b in zip(encrypted, key))
    return decrypted.decode()


# Grader prompt for <answer> tag format
GRADER_TEMPLATE = """
Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {question}

[response]: {response}

Your judgement must be in the format and criteria specified below:

extracted_final_answer: Extract the answer from the <answer>...</answer> tags in [response]. If no <answer> tags are found, extract the final answer from the response text. Put the extracted answer as 'None' if there is no answer to extract.

[correct_answer]: {correct_answer}

reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.
""".strip()


class LLMGrader:
    """LLM-based grader for judging answers."""

    def __init__(self, api_base: str, api_key: str, model_id: str):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.model_id = model_id

    def grade(self, question: str, response: str, correct_answer: str) -> Dict:
        """
        Grade whether the response is correct.

        Returns:
            Dict with 'correct' (bool), 'reasoning' (str), 'extracted_answer' (str)
        """
        grader_prompt = GRADER_TEMPLATE.format(
            question=question,
            response=response,
            correct_answer=correct_answer,
        )

        try:
            completion = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": grader_prompt}],
                temperature=0.0,
            )
            grading_response = completion.choices[0].message.content or ""

            # Extract the judgment
            correct_match = re.search(r"correct:\s*(yes|no)", grading_response, re.IGNORECASE)
            is_correct = correct_match.group(1).lower() == "yes" if correct_match else False

            # Extract reasoning
            reasoning_match = re.search(r"reasoning:\s*(.+?)(?=\ncorrect:|\n\n|$)", grading_response, re.DOTALL)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

            # Extract the extracted answer
            extracted_match = re.search(r"extracted_final_answer:\s*(.+?)(?=\n|$)", grading_response)
            extracted_answer = extracted_match.group(1).strip() if extracted_match else ""

            return {
                "correct": is_correct,
                "reasoning": reasoning,
                "extracted_answer": extracted_answer,
                "raw_response": grading_response,
            }
        except Exception as e:
            logger.error(f"Grading error: {e}")
            return {
                "correct": False,
                "reasoning": f"Grading error: {str(e)}",
                "extracted_answer": "",
                "raw_response": "",
            }


class OffSeekerSampler(SamplerBase):
    """Sampler wrapper for TrajectoryRecordingAgent."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        temperature: float = 0.6,
        enable_hint: bool = True,
        max_turns: int = 30,
    ):
        self.agent = TrajectoryRecordingAgent(
            api_base=api_base,
            api_key=api_key,
            model_id=model_id,
            temperature=temperature,
            enable_hint=enable_hint,
            max_turns=max_turns,
        )

    def _pack_message(self, role: str, content: str) -> Dict:
        return {"role": role, "content": content}

    def __call__(self, message_list: MessageList, sample_index: int = 0) -> SamplerResponse:
        task = message_list[0]["content"]
        logger.info(f"[Task {sample_index}] Running: {task[:50]}...")

        try:
            result = self.agent.run_with_trajectory(task, save_trajectory=False)
            answer = result.get("answer") or ""
            logger.info(f"[Task {sample_index}] Answer: {answer[:100]}...")

            return SamplerResponse(
                response_text=answer,
                actual_queried_message_list=message_list,
                response_metadata={"status": result.get("metadata", {}).get("status")}
            )
        except Exception as e:
            logger.error(f"[Task {sample_index}] Error: {e}")
            return SamplerResponse(
                response_text=f"Error: {str(e)}",
                actual_queried_message_list=message_list,
                response_metadata={"error": str(e)}
            )


def run_browsecomp_eval(
    # Model to evaluate
    model_api_base: str,
    model_api_key: str,
    model_id: str,
    # Grader model
    grader_api_base: str,
    grader_api_key: str,
    grader_model_id: str,
    # Evaluation settings
    num_examples: int = 100,
    temperature: float = 0.6,
    enable_hint: bool = True,
    max_turns: int = 30,
    max_workers: int = 5,  # 并发数
    output_file: str = None,
):
    """
    Run BrowseComp evaluation with LLM grader (concurrent execution).

    Args:
        model_api_base: API base URL for the model to evaluate
        model_api_key: API key for the model
        model_id: Model ID to evaluate
        grader_api_base: API base URL for the grader model
        grader_api_key: API key for the grader
        grader_model_id: Grader model ID
        num_examples: Number of examples (default 100)
        temperature: Sampling temperature
        enable_hint: Whether to use hint prompt
        max_turns: Maximum turns per task
        max_workers: Concurrent workers (default 5)
        output_file: Path to save results JSON
    """
    # Load dataset
    logger.info("Loading BrowseComp dataset...")
    df = pd.read_csv(
        "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
    )
    examples = [row.to_dict() for _, row in df.iterrows()]

    if num_examples:
        rng = random.Random(0)
        examples = rng.sample(examples, num_examples)

    logger.info(f"Loaded {len(examples)} examples")

    # Create sampler and grader
    sampler = OffSeekerSampler(
        api_base=model_api_base,
        api_key=model_api_key,
        model_id=model_id,
        temperature=temperature,
        enable_hint=enable_hint,
        max_turns=max_turns,
    )

    grader = LLMGrader(
        api_base=grader_api_base,
        api_key=grader_api_key,
        model_id=grader_model_id,
    )

    # Thread-safe storage
    results: List[Dict] = []
    results_lock = Lock()
    correct_count = 0
    correct_lock = Lock()

    def evaluate_single_example(i: int, example: Dict) -> Dict:
        """Evaluate a single example (thread-safe)."""
        nonlocal correct_count

        # Decrypt problem and answer
        canary = example.get("canary", "")
        problem = decrypt(example.get("problem", ""), canary)
        correct_answer = decrypt(example.get("answer", ""), canary)

        # Run task
        prompt_messages = [sampler._pack_message(content=problem, role="user")]
        response = sampler(prompt_messages, sample_index=i)
        extracted_answer = response.response_text

        # Grade answer with LLM
        grade_result = grader.grade(problem, extracted_answer, correct_answer)
        is_correct = grade_result["correct"]

        if is_correct:
            with correct_lock:
                correct_count += 1

        return {
            "sample_id": i,
            "problem": problem[:200],
            "correct_answer": correct_answer,
            "extracted_answer": extracted_answer,
            "grader_extracted_answer": grade_result["extracted_answer"],
            "is_correct": is_correct,
            "grader_reasoning": grade_result["reasoning"],
        }

    # Concurrent evaluation
    logger.info(f"Running with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(evaluate_single_example, i, example): i
            for i, example in enumerate(examples)
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating"):
            i = futures[future]
            try:
                result = future.result()
                with results_lock:
                    results.append(result)
            except Exception as e:
                logger.error(f"Task {i} failed: {e}")
                with results_lock:
                    results.append({
                        "sample_id": i,
                        "error": str(e),
                        "is_correct": False,
                    })

    # Sort results by sample_id
    results.sort(key=lambda x: x["sample_id"])

    # Calculate accuracy
    accuracy = correct_count / len(results)

    print(f"\n{'='*60}")
    print(f"Results: {correct_count}/{len(results)} correct ({accuracy:.2%})")
    print(f"{'='*60}\n")

    # Save results
    if output_file:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "model_id": model_id,
            "grader_model_id": grader_model_id,
            "num_examples": len(results),
            "correct_count": correct_count,
            "accuracy": accuracy,
            "results": results,
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Results saved to: {output_file}")

    return accuracy, results


def main():
    """Main entry point."""
    load_dotenv()

    # Model to evaluate
    model_api_base = os.getenv("OPENAI_BASE_URL") or os.getenv("API_BASE")
    model_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    model_id = os.getenv("MODEL_NAME", "deepseek-chat")

    # Grader model (can use a different model for grading)
    grader_api_base = os.getenv("GRADER_API_BASE") or model_api_base
    grader_api_key = os.getenv("GRADER_API_KEY") or model_api_key
    grader_model_id = os.getenv("GRADER_MODEL", "gpt-4o")

    if not model_api_base or not model_api_key:
        logger.error("Please set OPENAI_BASE_URL and OPENAI_API_KEY in .env file")
        return

    run_browsecomp_eval(
        model_api_base=model_api_base,
        model_api_key=model_api_key,
        model_id=model_id,
        grader_api_base=grader_api_base,
        grader_api_key=grader_api_key,
        grader_model_id=grader_model_id,
        num_examples=10,  # Start with 10 examples for testing
        temperature=0.6,
        enable_hint=True,
        max_turns=30,
        max_workers=5,  # Concurrent workers
        output_file="browsecomp_results.json",
    )


if __name__ == "__main__":
    main()
