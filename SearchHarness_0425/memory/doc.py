"""memory 包 —— 状态与节流层。

能力边界：
- 本包只包含「跨轮持久状态」模块。
- query_history：QueryRecord 与已发 query 的历史记录，供去重与 critics 使用。
- search_memory：检索记忆、候选池与证据（candidate / evidence）的滚动存储。
- search_crawl_controller：抓取节流与域名 / URL 调度限制。

不负责：
- 不做 LLM 评审（critics），不做剧情推进（agents）。
- 状态只在单次任务内有效，不负责任务间持久化。
"""
