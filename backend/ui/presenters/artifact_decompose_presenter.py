"""狗粮清理 Presenter"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.logger import log
from utils.settings_manager import settings

from backend.automation.artifact_decomposer import (
    ArtifactDecomposer,
    ExecuteWorker,
    SelectWorker,
)
from backend.database.repository.dogfood_rule_repo import DogfoodRuleRepo
from common.paths import ENGINES


class ArtifactDecomposePresenter(QObject):
    """圣遗物分解页面的 Presenter，调用 ArtifactDecomposer"""

    statusChanged = Signal()
    runningChanged = Signal()
    rulesChanged = Signal()
    selectedRuleNamesChanged = Signal()
    defaultActionChanged = Signal()
    selectionDoneChanged = Signal()
    pendingDiscardChanged = Signal()
    pendingKeepChanged = Signal()
    totalKeepChanged = Signal()
    totalDiscardChanged = Signal()
    maxDiscardCountChanged = Signal()

    MAX_RULE_SELECTION = 5

    _ACTION_LABELS: ClassVar[list[str]] = ["保留", "分解"]

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._status = ""
        self._decomposer = ArtifactDecomposer()
        self._select_worker: SelectWorker | None = None
        self._execute_worker: ExecuteWorker | None = None
        self._rules: list = []
        self._selected_rule_names: list[str] = []
        self._default_action = "keep"
        self._selection_done = False
        self._pending_keep = 0
        self._pending_discard = 0
        self._total_keep = 0
        self._total_discard = 0
        self._has_more_batches = False
        self._batch_number = 0
        self._active_rules: list = []
        self._active_default_action = ""
        self._max_discard_count = 1000
        self._load_rules()
        self._load_default_action()
        self._load_max_discard_count()

    # ========== 常量 ==========

    @Property(int, constant=True)
    def maxRuleSelection(self) -> int:
        return self.MAX_RULE_SELECTION

    # ========== 规则列表 ==========

    def _load_rules(self) -> None:
        """从数据库加载规则列表"""
        try:
            self._rules = DogfoodRuleRepo.find_all()
            log.debug(f"[Dogfood] 已加载 {len(self._rules)} 条规则")
        except Exception as e:
            log.error(f"[Dogfood] 加载规则列表失败: {e}")
            self._rules = []
        self.rulesChanged.emit()

    @Slot()
    def reloadRules(self) -> None:
        """进入页面时调用，刷新规则列表并清空选中"""
        self._selected_rule_names.clear()
        self._load_rules()
        self.selectedRuleNamesChanged.emit()

    @Property("QVariantList", notify=rulesChanged)
    def rules(self) -> list:
        """返回规则列表，每条规则转为 dict 供 QML 使用"""
        return [
            {
                "name": r.name,
                "action": r.action,
                "part": r.part,
                "part_exclude": r.part_exclude,
                "main_stat": r.main_stat,
                "set_name": r.set_name,
                "sub_stats": [s.to_dict() for s in r.sub_stats],
                "sub_count": r.sub_count,
                "priority": r.priority,
                "include_unactivated": r.include_unactivated,
                "include_main_stat": r.include_main_stat,
            }
            for r in self._rules
        ]

    # ========== 多选规则名 ==========

    @Property("QVariantList", notify=selectedRuleNamesChanged)
    def selectedRuleNames(self) -> list[str]:
        return list(self._selected_rule_names)

    @Slot(str)
    def toggleRuleSelection(self, name: str) -> None:
        """切换规则选中状态，最多选 MAX_RULE_SELECTION 条"""
        if name in self._selected_rule_names:
            self._selected_rule_names.remove(name)
        else:
            if len(self._selected_rule_names) >= self.MAX_RULE_SELECTION:
                log.warning(f"最多选择 {self.MAX_RULE_SELECTION} 条规则")
                return
            self._selected_rule_names.append(name)
        self.selectedRuleNamesChanged.emit()

    # ========== 默认行为 ==========

    @Property("QVariantList", constant=True)
    def defaultActionLabels(self) -> list[str]:
        return list(self._ACTION_LABELS)

    @Property(int, notify=defaultActionChanged)
    def defaultActionIndex(self) -> int:
        return 0 if self._default_action == "keep" else 1

    @Slot(int)
    def selectDefaultAction(self, index: int) -> None:
        self.setDefaultAction("keep" if index == 0 else "discard")

    def _load_default_action(self) -> None:
        self._default_action = settings.get("dogfood.default_action") or "keep"

    @Property(str, notify=defaultActionChanged)
    def defaultAction(self) -> str:
        return self._default_action

    @Slot(str)
    def setDefaultAction(self, action: str) -> None:
        if action == self._default_action:
            return
        self._default_action = action
        settings.set("dogfood.default_action", action)
        self.defaultActionChanged.emit()

    # ========== 每批分解数量上限 ==========

    def _load_max_discard_count(self) -> None:
        val = settings.get("dogfood.max_discard_count")
        try:
            self._max_discard_count = min(max(int(val), 1), 1000) if val else 1000
        except (ValueError, TypeError):
            self._max_discard_count = 1000

    @Property(int, notify=maxDiscardCountChanged)
    def maxDiscardCount(self) -> int:
        return self._max_discard_count

    @Slot(int)
    def setMaxDiscardCount(self, count: int) -> None:
        count = min(max(count, 1), 1000)
        if count == self._max_discard_count:
            return
        self._max_discard_count = count
        settings.set("dogfood.max_discard_count", count)
        self.maxDiscardCountChanged.emit()

    # ========== 选择确认状态 ==========

    @Property(bool, notify=selectionDoneChanged)
    def selectionDone(self) -> bool:
        return self._selection_done

    @Property(int, notify=pendingKeepChanged)
    def pendingKeep(self) -> int:
        return self._pending_keep

    @Property(int, notify=pendingDiscardChanged)
    def pendingDiscard(self) -> int:
        return self._pending_discard

    @Property(int, notify=totalKeepChanged)
    def totalKeep(self) -> int:
        return self._total_keep

    @Property(int, notify=totalDiscardChanged)
    def totalDiscard(self) -> int:
        return self._total_discard

    # ========== 运行状态 ==========

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    # ========== 分解入口 ==========

    @Slot()
    def startDecompose(self) -> None:
        """阶段一：进入分解页面并选择第一批圣遗物（后台线程执行）。"""
        if self._running:
            log.warning("分解已在运行中")
            return

        if not self._selected_rule_names:
            self._set_status("请至少选择一条规则")
            return

        db_rules = DogfoodRuleRepo.find_all()
        self._active_rules = [r for r in db_rules if r.name in self._selected_rule_names]
        if not self._active_rules:
            self._set_status("选中的规则已失效，请重新选择")
            return

        self._active_default_action = self._default_action
        self._total_keep = 0
        self._total_discard = 0
        self._batch_number = 0

        self._running = True
        self.runningChanged.emit()

        self._decomposer.reset_stop()

        log.info(
            f"[Dogfood] 开始分解: 规则={[r.name for r in self._active_rules]} "
            f"默认行为={self._active_default_action}"
        )

        self._select_worker = SelectWorker(
            self._decomposer,
            self._active_rules,
            self._active_default_action,
            self._max_discard_count,
            engines_dir=ENGINES,
        )
        self._select_worker.stepChanged.connect(self._set_status)
        self._select_worker.finished.connect(self._on_select_finished)
        self._select_worker.errorOccurred.connect(self._on_decompose_error)
        self._select_worker.start()

    def _on_select_finished(
        self, keep: int, discard: int, reached_limit: bool
    ) -> None:
        """SelectWorker 完成回调。"""
        self._select_worker = None

        if self._decomposer._stop_event.is_set():
            self._set_status("用户手动停止")
            self._finish()
            return

        self._total_keep += keep
        self._total_discard += discard
        self._pending_keep = keep
        self._pending_discard = discard
        self._has_more_batches = reached_limit
        self._selection_done = True

        log.info(
            f"[Dogfood] 第 {self._batch_number} 批选择完成: "
            f"保留={keep} 分解={discard} "
            f"上限={reached_limit} "
            f"累计保留={self._total_keep} 累计分解={self._total_discard}"
        )

        self.selectionDoneChanged.emit()
        self.pendingKeepChanged.emit()
        self.pendingDiscardChanged.emit()
        self.totalKeepChanged.emit()
        self.totalDiscardChanged.emit()

        if discard == 0:
            self._set_status("没有需要分解的圣遗物")
        else:
            self._set_status(
                f"已选中 {discard} 件待分解（保留 {keep} 件），请确认"
            )

    def _on_decompose_error(self, error: str) -> None:
        self._set_status(error)
        self._finish()

    @Slot()
    def confirmDecompose(self) -> None:
        """阶段二：用户确认后执行分解（后台线程），然后继续下一批或结束。"""
        if not self._selection_done:
            return

        log.info(f"[Dogfood] 用户确认分解: {self._pending_discard} 件")
        self._selection_done = False
        self.selectionDoneChanged.emit()

        if self._pending_discard > 0:
            self._execute_worker = ExecuteWorker(self._decomposer)
            self._execute_worker.stepChanged.connect(self._set_status)
            self._execute_worker.finished.connect(self._on_execute_finished)
            self._execute_worker.errorOccurred.connect(self._on_decompose_error)
            self._execute_worker.start()
        else:
            self._on_execute_finished(True)

    def _on_execute_finished(self, success: bool) -> None:
        self._execute_worker = None

        if not success:
            self._set_status("分解按钮点击失败")
            self._finish()
            return

        if self._has_more_batches:
            log.info(
                f"[Dogfood] 继续下一批 "
                f"(已完成 {self._total_keep + self._total_discard} 件)"
            )
            # 等待分解动画（可被热键中断）
            import time

            for _ in range(25):
                if self._decomposer._stop_event.is_set():
                    self._set_status("用户手动停止")
                    self._finish()
                    return
                time.sleep(0.1)

            self._batch_number += 1
            log.info(
                f"[Dogfood] 开始第 {self._total_keep + self._total_discard + 1} 批选择 "
                f"(规则={[r.name for r in self._active_rules]}, "
                f"默认={self._active_default_action})"
            )
            self._select_worker = SelectWorker(
                self._decomposer,
                self._active_rules,
                self._active_default_action,
                self._max_discard_count,
                engines_dir=ENGINES,
            )
            self._select_worker.stepChanged.connect(self._set_status)
            self._select_worker.finished.connect(self._on_select_finished)
            self._select_worker.errorOccurred.connect(self._on_decompose_error)
            self._select_worker.start()
        else:
            final_msg = (
                f"完成！保留 {self._total_keep} 件，分解 {self._total_discard} 件"
            )
            log.info(f"[Dogfood] {final_msg}")
            self._set_status(final_msg)
            self._finish()

    @Slot()
    def cancelDecompose(self) -> None:
        """取消分解，重置所有状态。"""
        if not self._selection_done:
            return
        log.info("[Dogfood] 用户取消分解")
        self._set_status("已取消")
        self._finish()

    @Slot()
    def _on_hotkey_stop(self) -> None:
        """热键停止回调（主线程，瞬间响应）。

        只请求 Worker 停止，不主动调用 _finish()。
        Worker 的 finished 信号会自然触发清理，避免 QThread 被提前销毁。
        """
        if self._select_worker is not None:
            self._select_worker.stop()
        if self._execute_worker is not None:
            self._execute_worker.stop()

    def _finish(self) -> None:
        """清理状态，结束分解流程。"""
        log.debug(
            f"[Dogfood] _finish: running={self._running} "
            f"batch={self._batch_number} "
            f"total_keep={self._total_keep} total_discard={self._total_discard}"
        )
        self._select_worker = None
        self._execute_worker = None
        self._batch_number = 0
        self._selection_done = False
        self._pending_keep = 0
        self._pending_discard = 0
        self._has_more_batches = False
        self._active_rules = []
        self._running = False
        self.runningChanged.emit()
        self.selectionDoneChanged.emit()
        self.pendingKeepChanged.emit()
        self.pendingDiscardChanged.emit()

    def _set_status(self, msg: str) -> None:
        self._status = msg
        self.statusChanged.emit()