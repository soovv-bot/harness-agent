"""critics 包 —— 评估与否决层。

能力边界：
- 本包只包含「读入产物 → 输出裁决」的评审模块，不驱动剧情。
- query_critic：评审具体检索 query 的质量（冗余 / 冲突 / 可执行性）。
- planning_direction_critic：评审整体推进方向，防止偏题。
- subtask_critic：评审子任务结果，决定接受 / 重做 / 跳过。

不负责：
- 不直接调用工具或改写 findings，只返回结构化 verdict，由 pipeline 消费。
- 不持有跨轮状态（历史在 memory 包）。
"""
