"""tools 包 —— 工具执行层。

能力边界：
- 本包只包含「agent 可调用工具的实现」。
- search_tools：search / visit_urls / search_wiki / execute_code 等工具函数。
- tool_processor：工具调用解析与调度。
- subprocess_interpreter：本地代码执行解释器。
- docker_interpreter：硬化 docker 沙箱解释器（CODE_EXEC_BACKEND=docker 时启用）。

不负责：
- 不感知 agent / pipeline，只按入参执行并返回结果。
"""
