"""llm 包 —— LLM 接入层。

能力边界：
- 本包只包含「与模型提供方交互」的模块。
- factory：build_openai_client 单点构造（测试在此打补丁）。
- client：统一 LLM 客户端封装。
- compat：thinking budget → reasoning effort 的兼容映射（_resolve_effort）。
- profiles：模型档案（model_profiles.yaml，随包分发）。
- errors：错误类型与重试约定。

不负责：
- 不感知业务语义，不拼接 prompt（prompt 在 agents/*.md）。
"""
