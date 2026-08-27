"""
基础设施调试 Presenter
=====================
为调试面板提供基础设施组件的测试方法：状态栏、GMessageBox 等。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot


class InfraDebugPresenter(QObject):
    """基础设施调试 Presenter — 供 QML 调试面板绑定"""

    @Slot(str)
    def testStatusBar(self, level: str) -> None:
        """测试状态栏：通过 log.xxx 发送消息，测试完整的日志桥接链路"""
        from utils.logger import log

        msg = f"[调试] 状态栏颜色测试 — {level}"
        if level == "SUCCESS":
            log.success(msg)
        elif level == "WARNING":
            log.warning(msg)
        elif level == "ERROR":
            log.error(msg)
        elif level == "CRITICAL":
            log.critical(msg)
        else:
            log.info(msg)

    @Slot(str)
    def testGMessageBox(self, msg_type: str) -> None:
        """测试 GMessageBox Python 桥接链路：Python → Signal → QML"""
        from ui.gmessagebox import GMessageBox

        messages = {
            "info": "[基础设施调试] Python桥接 — 信息消息",
            "success": "[基础设施调试] Python桥接 — 成功消息",
            "warning": "[基础设施调试] Python桥接 — 警告消息",
            "error": "[基础设施调试] Python桥接 — 错误消息",
        }
        msg = messages.get(msg_type, messages["info"])
        getattr(GMessageBox, msg_type)(msg)
