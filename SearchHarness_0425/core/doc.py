"""core 包 —— 项目基础设施层。

能力边界：
- 本包只包含「所有层都依赖的底座」模块。
- config：全局配置与 settings 单例。
- benchmark_registry：benchmark 注册表与样本缓存定位（_REPO_ROOT 已按 core/ 层级修正）。
- results_schema：结果 schema 与 replay 不变量（VOLATILE_TOP_LEVEL 键名是对比基线，禁止改字符串）。

不负责：
- 不包含任何业务逻辑；被依赖可以，依赖上层业务包不可以。
"""
