"""Executable entry points grouped by purpose (RD step5).

* ``scripts.run``      — benchmark evaluation entry points
* ``scripts.smoke``    — connectivity / end-to-end smoke checks
* ``scripts.analysis`` — offline analysis & maintenance utilities

All modules are meant to be invoked as ``python -m scripts.<group>.<name>``
so that the project root stays on ``sys.path`` and top-level modules
(``config``, ``benchmark_registry``, ``results_schema``, ...) remain
importable.
"""
