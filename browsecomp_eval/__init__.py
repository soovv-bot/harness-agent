"""
BrowseComp Evaluation Framework for OffSeeker-trained models

This module provides evaluation utilities for testing trained models on the BrowseComp benchmark.

Key Components:
- BrowseCompEval: Main evaluation class
- SamplerBase: Base class for model samplers
- eval_types: Type definitions for evaluation

Usage:
    from browsecomp_eval import BrowseCompEval, SamplerBase

    # Create a sampler wrapper for your trained model
    class MyModelSampler(SamplerBase):
        def __call__(self, message_list, sample_index):
            # Call your model and return response
            ...

    # Run evaluation
    evaluator = BrowseCompEval(grader_model=grader, num_examples=100)
    results = evaluator(sampler=MyModelSampler())
"""

from .eval_types import SamplerBase, SamplerResponse, EvalResult, SingleEvalResult
from .browsecamp_eval import BrowseCompEval, QUERY_TEMPLATE, GRADER_TEMPLATE
from .common import aggregate_results, map_with_progress

__all__ = [
    'SamplerBase',
    'SamplerResponse',
    'EvalResult',
    'SingleEvalResult',
    'BrowseCompEval',
    'QUERY_TEMPLATE',
    'GRADER_TEMPLATE',
    'aggregate_results',
    'map_with_progress',
]
