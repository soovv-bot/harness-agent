"""Benchmark evaluation entry points (RD step5).

``run_benchmark`` is the unified CLI dispatching to the mode runners;
``run_browsecomp`` / ``run_browsecomp_fixed_sample`` / ``run_seed_repeats``
implement the sample / fixed / repeats modes; ``run_checkpoint`` provides
resumable fixed-sample runs; ``run_single_verify`` re-runs single tasks.
"""
