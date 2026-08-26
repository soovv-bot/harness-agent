"""contract 包 —— 数据契约层（R1 纯凈）。

能力边界：
- 本包只包含「纯数据结构」：QueryRecord / QueryVerdict / Plan / Subtask / ToolResult / TrajectoryDoc 等。
- R1 约束：contract 禁止 import 本项目任何其他模块， tests/test_contract.py 在 AST 层强制检查。

不负责：
- 不含任何 IO / LLM / 业务逻辑。
"""
