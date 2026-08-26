"""scripts.run 子包 —— 正式跑数入口。

能力边界：
- run_benchmark.py：benchmark × mode 的总调度入口。
- run_browsecomp*.py / run_seed_repeats.py / run_checkpoint.py / run_single_verify.py：各跑数模式。

不负责：
- 不写评审 / 编排逻辑，统一调用 pipeline 与各包能力。
"""
