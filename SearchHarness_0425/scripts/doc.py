"""scripts 包 —— 入口脚本层。

能力边界：
- 本包只包含「命令行可执行入口」，分子目录：
  - run/：正式跑数入口（run_benchmark 及各 benchmark runner）。
  - smoke/：冒烟与调试入口（smoke_test_simple 等）。
  - analysis/：离线分析（failure_taxonomy / judge_calibration 等）。

不负责：
- 业务逻辑必须下沉到 pipeline / agents / critics / memory 等包，脚本只做解析参数与调度。
"""
