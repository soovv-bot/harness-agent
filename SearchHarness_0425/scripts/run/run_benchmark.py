"""Unified benchmark evaluation CLI (M1).

Single entry point over the per-mode runners; benchmark metadata comes from
benchmark_registry. All flags after the mode are forwarded verbatim, so the
legacy `python -m scripts.run.run_browsecomp ...` invocations keep working unchanged.

Usage:
    python -m scripts.run.run_benchmark --list
    python -m scripts.run.run_benchmark browsecomp sample  --num-examples 5 --max-workers 1
    python -m scripts.run.run_benchmark browsecomp fixed   --seed 123 --sample-size 10 --positions 1-3 --output out.json
    python -m scripts.run.run_benchmark browsecomp repeats --seed 123 --repeats 10
"""

from __future__ import annotations

import argparse
import importlib
import sys

from benchmark_registry import get_benchmark, list_benchmarks

# mode -> module exposing main()
_MODES = {
    "sample": "scripts.run.run_browsecomp",
    "fixed": "scripts.run.run_browsecomp_fixed_sample",
    "repeats": "scripts.run.run_seed_repeats",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_benchmark.py",
        description="Unified benchmark evaluation entry point",
        add_help=False,  # let the child mode's parser own -h/--help
    )
    raw = sys.argv[1:]
    parser.add_argument("-h", "--help", action="store_true", dest="show_help",
                        help="Show this help (also pass -h after MODE for mode-specific flags)")
    parser.add_argument("--list", action="store_true", help="List registered benchmarks and modes")
    parser.add_argument("benchmark", nargs="?", help="Benchmark name (see --list)")
    parser.add_argument("mode", nargs="?", choices=sorted(_MODES), help="Run mode")
    args, rest = parser.parse_known_args(raw)

    if args.show_help and not (args.benchmark and args.mode):
        parser.print_help()
        return

    if args.list:
        modes = ", ".join(sorted(_MODES))
        for spec in list_benchmarks():
            print(f"{spec.name}\t{spec.display_name}\tmodes: {modes}")
        return

    if not args.benchmark or not args.mode:
        parser.error("benchmark and mode are required (or use --list)")

    if args.show_help:
        rest = [*rest, "--help"]  # forward to the child parser

    get_benchmark(args.benchmark)  # raises KeyError naming registered benchmarks
    mode = _MODES[args.mode]
    module = importlib.import_module(mode)
    sys.argv = [f"{mode.rsplit('.', 1)[-1]}.py", *rest]
    module.main()


if __name__ == "__main__":
    main()
