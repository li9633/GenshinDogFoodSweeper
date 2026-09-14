"""功能模块（capability / feature）
================================
每个子包是一个**功能**：对外只暴露少量入口，内部由契约（``backend/contracts``）
与底层能力（``backend/automation`` / ``backend/domain`` / ``backend/platform``）拼装而成。

当前：

- :mod:`backend.features.artifact_save` —— 扫描结果保存（格式注册表 + 内置格式）。
"""
