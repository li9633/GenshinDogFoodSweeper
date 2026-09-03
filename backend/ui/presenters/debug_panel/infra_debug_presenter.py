"""
基础设施调试 Presenter
=====================
为调试面板提供基础设施组件的测试方法：状态栏、GMessageBox 等。
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


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

    @Slot(str, int)
    def testGMessageBoxDelayed(self, msg_type: str, delay_sec: int) -> None:
        """测试 GMessageBox 聚焦延迟调用

        延迟指定秒数后触发弹窗，便于切换到其他窗口测试窗口是否被拉到前台。
        错误/警告类型会触发 requestActivate → 窗口拉起；信息/成功类型不会。
        """
        from PySide6.QtCore import QTimer
        from ui.gmessagebox import GMessageBox

        messages = {
            "info": "[聚焦测试] 延迟后 — 信息消息（不激活窗口）",
            "success": "[聚焦测试] 延迟后 — 成功消息（不激活窗口）",
            "warning": "[聚焦测试] 延迟后 — 警告消息（应激活窗口）",
            "error": "[聚焦测试] 延迟后 — 错误消息（应激活窗口）",
        }
        msg = messages.get(msg_type, messages["info"])

        def _do_show():
            getattr(GMessageBox, msg_type)(msg)

        QTimer.singleShot(delay_sec * 1000, _do_show)

    # ============================================================
    # GProgressBar 调试
    # ============================================================

    _debug_progress_value: float = 0.38
    _debug_progress_text: str = "翠绿之影  24 / 63"
    _debug_indeterminate: bool = False

    debugProgressChanged = Signal()

    @Property(float, notify=debugProgressChanged)
    def debugProgressValue(self) -> float:
        return self._debug_progress_value

    @Property(str, notify=debugProgressChanged)
    def debugProgressText(self) -> str:
        return self._debug_progress_text

    @Property(bool, notify=debugProgressChanged)
    def debugIndeterminate(self) -> bool:
        return self._debug_indeterminate

    @Slot()
    def simulateIndeterminateProgress(self) -> None:
        """模拟不确定进度：滚动条 + 加载文字"""
        self._debug_indeterminate = True
        self._debug_progress_text = "正在拉取圣遗物套装…"
        self.debugProgressChanged.emit()

    @Slot()
    def simulateDeterminateProgress(self) -> None:
        """模拟确定进度：固定进度条 + 当前进度文字"""
        self._debug_indeterminate = False
        self._debug_progress_value = 0.38
        self._debug_progress_text = "翠绿之影  24 / 63"
        self.debugProgressChanged.emit()

    @Slot()
    def simulateCompletedProgress(self) -> None:
        """模拟完成：100% 进度条 + 完成文字"""
        self._debug_indeterminate = False
        self._debug_progress_value = 1.0
        self._debug_progress_text = "同步完成"
        self.debugProgressChanged.emit()

    # ============================================================
    # 数据库 & 模型清理
    # ============================================================

    @Slot()
    def clearArtifactSets(self) -> None:
        """清空圣遗物套装表（artifact_sets）"""
        from database.repository.artifact_set_repo import ArtifactSetRepo
        from utils.logger import log

        count = ArtifactSetRepo.delete_all()
        log.info(f"[调试] 已清空 artifact_sets 表（{count} 条记录）")

    @Slot()
    def clearArtifactPieces(self) -> None:
        """清空圣遗物单件表（artifact_pieces）"""
        from database.repository.artifact_piece_repo import ArtifactPieceRepo
        from utils.logger import log

        count = ArtifactPieceRepo.delete_all()
        log.info(f"[调试] 已清空 artifact_pieces 表（{count} 条记录）")

    @Slot()
    def deleteOcrModel(self) -> None:
        """删除 OCR 模型文件（engine/official_models 目录）"""
        import shutil
        from pathlib import Path

        from utils.logger import log

        engines_dir = Path(__file__).resolve().parents[3] / "engines"
        models_dir = engines_dir / "official_models"
        if models_dir.exists():
            shutil.rmtree(models_dir)
            log.info("[调试] 已删除 OCR 模型目录: official_models")
        else:
            log.info("[调试] OCR 模型目录不存在，无需删除")