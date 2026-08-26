"""pipeline 包 —— 流程编排层。

能力边界：
- 本包只包含「把 agents / critics / memory / tools 串成一次任务流程」的编排模块。
- orchestrator：主编排循环。
- stages / subtasks / candidates / feedback / finish / verification / tracing：各阶段与横切逻辑。

不负责：
- 不自己实现 agent / critic 逻辑，只做编排与数据流转。
"""
