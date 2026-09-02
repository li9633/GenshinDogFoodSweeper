"""圣遗物锁定 Presenter"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.logger import log
from utils.settings_manager import settings

from backend.automation.artifact_locker import ArtifactLocker
from backend.database.repository.dogfood_rule_repo import DogfoodRuleRepo


class LockerPresenter(QObject):
    """圣遗物锁定页面的 Presenter，调用 ArtifactLocker"""

    statusChanged = Signal()
    runningChanged = Signal()
    rulesChanged = Signal()
    selectedRuleNamesChanged = Signal()
    defaultActionChanged = Signal()
    reUnlockChanged = Signal()
    statsChanged = Signal()
    limitCountEnabledChanged = Signal()
    maxCountChanged = Signal()

    MAX_RULE_SELECTION = 5

    _ACTION_LABELS: ClassVar[list[str]] = ["锁定", "解锁"]

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._status = ""
        self._locker = ArtifactLocker()
        self._rules: list = []
        self._selected_rule_names: list[str] = []
        self._default_action = "keep"
        self._re_unlock = False
        self._locked_count = 0
        self._unlocked_count = 0
        self._skipped_count = 0
        self._limit_count_enabled = False
        self._max_count = 100
        self._load_rules()
        self._load_default_action()
        self._load_re_unlock()
        self._load_limit_count()

    # ========== 常量 ==========

    @Property(int, constant=True)
    def maxRuleSelection(self) -> int:
        return self.MAX_RULE_SELECTION

    # ========== 规则列表 ==========

    def _load_rules(self) -> None:
        try:
            self._rules = DogfoodRuleRepo.find_all()
            log.debug(f"[Locker] 已加载 {len(self._rules)} 条规则")
        except Exception as e:
            log.error(f"[Locker] 加载规则列表失败: {e}")
            self._rules = []
        self.rulesChanged.emit()

    @Slot()
    def reloadRules(self) -> None:
        self._selected_rule_names.clear()
        self._load_rules()
        self.selectedRuleNamesChanged.emit()

    @Property("QVariantList", notify=rulesChanged)
    def rules(self) -> list:
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

    # ========== 重新解锁选项 ==========

    def _load_re_unlock(self) -> None:
        val = settings.get("locker.re_unlock")
        self._re_unlock = val == "true"

    @Property(bool, notify=reUnlockChanged)
    def reUnlock(self) -> bool:
        return self._re_unlock

    @Slot(bool)
    def setReUnlock(self, value: bool) -> None:
        if value == self._re_unlock:
            return
        self._re_unlock = value
        settings.set("locker.re_unlock", "true" if value else "false")
        self.reUnlockChanged.emit()

    # ========== 限制处理数量 ==========

    def _load_limit_count(self) -> None:
        val = settings.get("locker.limit_count_enabled")
        self._limit_count_enabled = val == "true"
        val = settings.get("locker.max_count")
        try:
            self._max_count = min(max(int(val), 1), 9999) if val else 100
        except (ValueError, TypeError):
            self._max_count = 100

    @Property(bool, notify=limitCountEnabledChanged)
    def limitCountEnabled(self) -> bool:
        return self._limit_count_enabled

    @Slot(bool)
    def setLimitCountEnabled(self, value: bool) -> None:
        if value == self._limit_count_enabled:
            return
        self._limit_count_enabled = value
        settings.set("locker.limit_count_enabled", "true" if value else "false")
        self.limitCountEnabledChanged.emit()

    @Property(int, notify=maxCountChanged)
    def maxCount(self) -> int:
        return self._max_count

    @Slot(int)
    def setMaxCount(self, count: int) -> None:
        count = min(max(count, 1), 9999)
        if count == self._max_count:
            return
        self._max_count = count
        settings.set("locker.max_count", count)
        self.maxCountChanged.emit()

    # ========== 统计 ==========

    @Property(int, notify=statsChanged)
    def lockedCount(self) -> int:
        return self._locked_count

    @Property(int, notify=statsChanged)
    def unlockedCount(self) -> int:
        return self._unlocked_count

    @Property(int, notify=statsChanged)
    def skippedCount(self) -> int:
        return self._skipped_count

    # ========== 运行状态 ==========

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    # ========== 锁定入口 ==========

    @Slot()
    def startLock(self) -> None:
        if self._running:
            log.warning("锁定已在运行中")
            return

        if not self._selected_rule_names:
            self._set_status("请至少选择一条规则")
            return

        db_rules = DogfoodRuleRepo.find_all()
        active_rules = [r for r in db_rules if r.name in self._selected_rule_names]
        if not active_rules:
            self._set_status("选中的规则已失效，请重新选择")
            return

        self._locked_count = 0
        self._unlocked_count = 0
        self._skipped_count = 0
        self.statsChanged.emit()

        self._running = True
        self.runningChanged.emit()

        self._locker.reset_stop()

        try:
            log.info(
                f"[Locker] 开始锁定: 规则={[r.name for r in active_rules]} "
                f"默认行为={self._default_action} 重新解锁={self._re_unlock}"
            )

            self._set_status("正在扫描并锁定圣遗物...")
            max_count = self._max_count if self._limit_count_enabled else 0
            locked, unlocked, skipped = self._locker.lock_artifacts(
                active_rules, self._default_action, self._re_unlock, max_count
            )

            if self._locker._fatal_error:
                self._set_status(self._locker._fatal_error)
                self._finish()
                return

            self._locked_count = locked
            self._unlocked_count = unlocked
            self._skipped_count = skipped
            self.statsChanged.emit()

            msg = f"完成！锁定 {locked} 件，解锁 {unlocked} 件，跳过 {skipped} 件"
            log.info(f"[Locker] {msg}")
            self._set_status(msg)
            self._finish()
        except Exception:
            self._set_status("锁定流程异常")
            self._finish()

    @Slot()
    def stopLock(self) -> None:
        self._locker.stop()
        log.info("[Locker] 已请求停止")

    @Slot()
    def _on_hotkey_stop(self) -> None:
        if self._running:
            self._set_status("用户手动停止")
            self._finish()

    def _finish(self) -> None:
        self._locker.reset_stop()
        self._running = False
        self.runningChanged.emit()

    def _set_status(self, msg: str) -> None:
        self._status = msg
        self.statusChanged.emit()
