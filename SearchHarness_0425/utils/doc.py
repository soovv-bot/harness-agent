"""utils 包 —— 无状态基础支撑层。

能力边界：
- 本包只包含「无对话状态、可被任意层调用」的工具模块。
- answer_verifier：答案抽取与格式校验（<answer> 标签等）。
- disk_cache：磁盘缓存（LLM 响应 / 抓取结果）。
- stats_utils：确定性 bootstrap 置信区间等统计。
- llm_usage：token 与成本统计，定价表 model_pricing.yaml 与本模块同目录。

不负责：
- 不 import agents / critics / memory / pipeline，禁止反向依赖。
"""
