"""Concurrency utilities

This module provides utilities for concurrent processing using ThreadPoolExecutor.
It includes a helper class for managing concurrent tasks and a simple function
for running processing tasks in parallel.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Any, Optional
from tqdm import tqdm
from loguru import logger
from threading import Lock


# ============================================================================
# Concurrent Processing Class
# ============================================================================

class ConcurrentProcessor:
    """Helper class for concurrent processing with progress tracking

    This class wraps ThreadPoolExecutor and provides a simpler interface
    for processing items concurrently with optional progress bar.

    Attributes:
        max_workers: Maximum number of worker threads
        desc: Description for progress bar
        file_lock: Thread lock for file operations
    """

    def __init__(self, max_workers: Optional[int] = None, desc: str = "Processing"):
        """Initialize the ConcurrentProcessor

        Args:
            max_workers: Maximum number of worker threads (default: 10)
            desc: Description for progress bar
        """
        self.max_workers = max_workers or 10
        self.desc = desc
        self.file_lock = Lock()

    def process_items(
        self,
        items: List[Any],
        process_func: Callable,
        show_progress: bool = True
    ):
        """Process items concurrently

        Args:
            items: List of items to process
            process_func: Function to call for each item
            show_progress: Whether to show progress bar
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {executor.submit(process_func, item): item for item in items}

            # Process completed futures
            iterator = as_completed(futures)
            if show_progress:
                iterator = tqdm(iterator, total=len(items), desc=self.desc)

            for future in iterator:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing item: {e}")

    def process_items_with_results(
        self,
        items: List[Any],
        process_func: Callable,
        show_progress: bool = True
    ) -> List[Any]:
        """Process items concurrently and return results

        Args:
            items: List of items to process
            process_func: Function to call for each item (should return a value)
            show_progress: Whether to show progress bar

        Returns:
            List of results from successful processing
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(process_func, item): item
                for item in items
            }

            iterator = as_completed(future_to_item)
            if show_progress:
                iterator = tqdm(iterator, total=len(items), desc=self.desc)

            for future in iterator:
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing item: {e}")

        return results


# ============================================================================
# Convenience Functions
# ============================================================================

def run_concurrently(
    items: List[Any],
    process_func: Callable,
    max_workers: int,
    desc: str = "Processing"
):
    """Simple function to run processing concurrently

    This is a convenience function that creates a ConcurrentProcessor
    and runs items through it.

    Args:
        items: List of items to process
        process_func: Function to call for each item
        max_workers: Maximum number of worker threads
        desc: Description for progress bar
    """
    processor = ConcurrentProcessor(max_workers=max_workers, desc=desc)
    processor.process_items(items, process_func, show_progress=True)


def run_concurrently_with_results(
    items: List[Any],
    process_func: Callable,
    max_workers: int,
    desc: str = "Processing"
) -> List[Any]:
    """Simple function to run processing concurrently and return results

    This is a convenience function that creates a ConcurrentProcessor
    and returns the results.

    Args:
        items: List of items to process
        process_func: Function to call for each item (should return a value)
        max_workers: Maximum number of worker threads
        desc: Description for progress bar

    Returns:
        List of results from successful processing
    """
    processor = ConcurrentProcessor(max_workers=max_workers, desc=desc)
    return processor.process_items_with_results(items, process_func, show_progress=True)


# ============================================================================
# Legacy/Backward Compatibility
# ============================================================================

# Global file lock for legacy code compatibility
file_lock = Lock()


__all__ = [
    'ConcurrentProcessor',
    'run_concurrently',
    'run_concurrently_with_results',
    'file_lock',
]
