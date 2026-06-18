"""File I/O utilities

This module provides utilities for reading and writing JSON and JSONL files,
as well as helper functions for tracking processed entities.
"""

import json
import os
from typing import Any, Dict, List, Set
from pathlib import Path
from loguru import logger

from deepforge.config import settings


# ============================================================================
# Directory Management
# ============================================================================

def ensure_directories():
    """Ensure all required directories exist

    Creates data and tmp directories if they don't exist.
    """
    settings.paths.ensure_directories()


# ============================================================================
# JSON File Operations
# ============================================================================

def load_json(file_path: Path) -> Any:
    """Load data from JSON file

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data, or None if file doesn't exist
    """
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(file_path: Path, data: Any, indent: int = 4):
    """Write data to JSON file

    Args:
        file_path: Path to the JSON file
        data: Data to write (must be JSON-serializable)
        indent: Number of spaces for indentation (default: 4)
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


# ============================================================================
# JSONL File Operations
# ============================================================================

def load_jsonl(file_path: Path) -> List[Dict]:
    """Load data from JSONL file

    Args:
        file_path: Path to the JSONL file

    Returns:
        List of dictionaries (one per line)
    """
    data = []
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return data

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data.append(json.loads(line.strip()))
            except json.JSONDecodeError as e:
                logger.warning(f"Error parsing line in {file_path}: {e}")

    return data


def write_jsonl(file_path: Path, data: List[Dict], mode: str = "w"):
    """Write data to JSONL file

    Args:
        file_path: Path to the JSONL file
        data: List of dictionaries to write
        mode: Write mode ('w' for overwrite, 'a' for append)
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, mode, encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def append_jsonl(file_path: Path, item: Dict):
    """Append single item to JSONL file

    Args:
        file_path: Path to the JSONL file
        item: Dictionary to append
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


# ============================================================================
# Processed Data Tracking
# ============================================================================

def get_processed_entities(file_path: Path) -> Set[str]:
    """Get set of already processed entity names

    Args:
        file_path: Path to the JSONL file with processed data

    Returns:
        Set of entity names that have been processed
    """
    processed = set()
    if not file_path.exists():
        return processed

    data = load_jsonl(file_path)
    for item in data:
        if "entity" in item:
            processed.add(item["entity"])

    return processed


def get_processed_data_ids(file_path: Path, id_key: str = "question") -> Set[str]:
    """Get set of already processed data IDs

    Args:
        file_path: Path to the JSONL file with processed data
        id_key: Key to use as the unique identifier (default: "question")

    Returns:
        Set of IDs that have been processed
    """
    processed = set()
    if not file_path.exists():
        return processed

    data = load_jsonl(file_path)
    for item in data:
        if id_key in item:
            processed.add(item[id_key])

    return processed


# ============================================================================
# Legacy/Backward Compatibility Functions
# ============================================================================

# Original functions from trajectory_generation.py and qa_difficulty_enhancement.py
def get_processed_entities_legacy(save_path: str) -> set:
    """Legacy version of get_processed_entities (for backward compatibility)

    Args:
        save_path: String path to the file

    Returns:
        Set of processed entity names
    """
    return get_processed_entities(Path(save_path))


__all__ = [
    'ensure_directories',
    'load_json',
    'write_json',
    'load_jsonl',
    'write_jsonl',
    'append_jsonl',
    'get_processed_entities',
    'get_processed_data_ids',
    'get_processed_entities_legacy',
]
