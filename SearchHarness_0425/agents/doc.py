"""agents 包 —— 行为主体层（规划 / 执行 / 收尾）。

能力边界：
- 本包只包含「会发起 LLM 对话并驱动剧情前进」的主体模块。
- planning_agent：将用户问题拆解为子任务（subtask 队列），输出结构化计划。
- search_agent：执行单个子任务，驱动 search / visit_urls / search_wiki 等工具多轮交互，产出 findings。
- search_finalizer：在所有子任务结束后收敛全文，生成最终答案。

不负责：
- 不评估 / 否决中间产物（那是 critics 包的职责）。
- 不维护跨轮记忆与节流状态（那是 memory 包的职责）。
- 不直接发起 HTTP / 工具调用（统一走 llm.factory 与 tools 包）。

配套资源：同目录下的 *_prompt.md 是各 agent 的系统提示词，路径按 __file__ 相对定位，移动模块时必须随之移动。
"""
