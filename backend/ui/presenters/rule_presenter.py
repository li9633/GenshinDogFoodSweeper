"""狗粮规则 Presenter"""

from __future__ import annotations

import json
from pathlib import Path

from database.repository.dogfood_rule_repo import DogfoodRuleRepo
from models.dogfood_rule import DogfoodRule
from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.logger import log
from utils.settings_manager import settings

from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
from backend.automation.recognizer import ArtifactRecognizer
from backend.models.artifact_recognition_field import ArtifactRecognitionField
from backend.models.slot_models import ALL_SLOT_CONFIGS


class RulePresenter(QObject):
    rulesChanged = Signal()
    selectedRuleChanged = Signal()
    defaultActionChanged = Signal()
    statusMessage = Signal(str, int, str)  # msg, duration, level
    testResultReady = Signal("QVariantMap")  # 测试结果
    testStatusChanged = Signal(str)  # 测试状态提示

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rules: list[DogfoodRule] = []
        self._selected_name = ""
        self._default_action = "keep"
        self._stats_config: dict | None = None
        self._selected_config_index = 0
        self._load()

    # ========== 持久化 ==========

    def _load(self) -> None:
        self._default_action = settings.get("dogfood.default_action") or "keep"
        self._reload()

    def _reload(self) -> None:
        """从数据库重新加载规则列表"""
        try:
            self._rules = DogfoodRuleRepo.find_all()
            log.debug(f"已加载 {len(self._rules)} 条规则")
        except Exception as e:
            log.error(f"加载规则列表失败: {e}")
            self._rules = []
        self.rulesChanged.emit()

    # ========== Properties ==========

    @Property("QVariantList", notify=rulesChanged)
    def rules(self) -> list[dict]:
        try:
            result = [r.to_dict() | {"_index": i} for i, r in enumerate(self._rules)]
            log.debug(f"rules 属性返回 {len(result)} 条: {[r.get('name') for r in result]}")
            return result
        except Exception as e:
            log.error(f"序列化规则列表失败: {e}")
            return []

    def _load_stats_config(self) -> dict:
        if self._stats_config is None:
            stats_path = (
                Path(__file__).parent.parent.parent.parent
                / "resources" / "templates" / "config" / "artifact_stats.json"
            )
            self._stats_config = json.loads(stats_path.read_text(encoding="utf-8"))
        return self._stats_config

    @Property("QVariantList", notify=rulesChanged)
    def artifactSetNames(self) -> list[dict]:
        try:
            from database.repository.artifact_set_repo import ArtifactSetRepo
            return [{"name": s.name, "icon": s.icon} for s in ArtifactSetRepo.find_all()]
        except Exception:
            return []

    @Property("QVariantList", notify=rulesChanged)
    def subStatNames(self) -> list[str]:
        try:
            return self._load_stats_config().get("sub_stat_names", [])
        except Exception:
            return []

    @Property("QVariantMap", notify=rulesChanged)
    def mainStatsByPiece(self) -> dict:
        try:
            return self._load_stats_config().get("main_stats_by_piece", {})
        except Exception:
            return {}

    @Property("QVariantMap", notify=rulesChanged)
    def statCategories(self) -> dict:
        try:
            return self._load_stats_config().get("stats", {})
        except Exception:
            return {}

    @Property("QVariantMap", notify=selectedRuleChanged)
    def selectedRule(self) -> dict:
        for r in self._rules:
            if r.name == self._selected_name:
                return r.to_dict()
        return {}

    @Property(str, notify=defaultActionChanged)
    def defaultAction(self) -> str:
        return self._default_action

    # ========== CRUD ==========

    @Slot("QVariantMap", result="QVariantMap")
    def saveRule(self, rule_map: dict) -> dict:
        """保存规则（新增或更新），名称为主键"""
        try:
            name = rule_map.get("name", "").strip()
            if not name:
                log.warning("请输入规则名称")
                return {"ok": False, "message": "请输入规则名称"}

            original_name = rule_map.get("_original_name", "")
            log.debug(f"saveRule 收到: name={name}, _original_name={original_name}, keys={list(rule_map.keys())}")

            # 解析副词条：QML 传来 [{name, op?, value?}, ...] 对象列表
            subs = rule_map.get("sub_stats", [])
            if isinstance(subs, list):
                rule_map["sub_stats"] = [s for s in subs if isinstance(s, dict)]

            rule = DogfoodRule.from_dict(rule_map)
            rule.name = name

            # 编辑模式：名称未变，直接更新
            if original_name and original_name == name:
                DogfoodRuleRepo.upsert(rule)
                self._reload()
                return {"ok": True, "message": "规则已保存"}

            # 编辑模式：名称已变，需检查新名称是否冲突，再删旧存新
            if original_name and original_name != name:
                if DogfoodRuleRepo.exists(name):
                    log.warning(f"规则名称「{name}」已存在，请更换名称")
                    return {"ok": False, "message": f"规则名称「{name}」已存在，请更换名称"}
                DogfoodRuleRepo.delete(original_name)
                DogfoodRuleRepo.upsert(rule)
                self._reload()
                return {"ok": True, "message": "规则已保存"}

            # 新建模式：检查名称是否重复
            if DogfoodRuleRepo.exists(name):
                log.warning(f"规则名称「{name}」已存在，请更换名称")
                return {"ok": False, "message": f"规则名称「{name}」已存在，请更换名称"}
            DogfoodRuleRepo.upsert(rule)
            self._reload()
            return {"ok": True, "message": "规则已保存"}
        except Exception as e:
            log.error(f"保存规则失败: {e}")
            return {"ok": False, "message": f"保存失败: {e}"}

    @Slot(str, result=bool)
    def deleteRule(self, name: str) -> bool:
        try:
            DogfoodRuleRepo.delete(name)
            if self._selected_name == name:
                self._selected_name = ""
                self.selectedRuleChanged.emit()
            self._reload()
            return True
        except Exception as e:
            log.error(f"删除规则失败: {e}")
            return False

    @Slot(str, result=str)
    def duplicateRule(self, name: str) -> str:
        for r in self._rules:
            if r.name == name:
                new_name = f"{name} (副本)"
                counter = 1
                while any(r2.name == new_name for r2 in self._rules):
                    counter += 1
                    new_name = f"{name} (副本{counter})"
                new_rule = DogfoodRule.from_dict(r.to_dict())
                new_rule.name = new_name
                DogfoodRuleRepo.upsert(new_rule)
                self._reload()
                return new_name
        return ""

    @Slot(str)
    def selectRule(self, name: str) -> None:
        self._selected_name = name
        self.selectedRuleChanged.emit()

    @Slot()
    def prepareNewRule(self) -> None:
        """清空选中，准备新建规则"""
        self._selected_name = ""
        self.selectedRuleChanged.emit()

    # ========== 优先级 ==========

    @Slot(str)
    def moveRuleUp(self, name: str) -> None:
        for i, r in enumerate(self._rules):
            if r.name == name and i > 0:
                prev = self._rules[i - 1]
                r.priority, prev.priority = prev.priority, r.priority
                DogfoodRuleRepo.upsert(r)
                DogfoodRuleRepo.upsert(prev)
                self._reload()
                return

    @Slot(str)
    def moveRuleDown(self, name: str) -> None:
        for i, r in enumerate(self._rules):
            if r.name == name and i < len(self._rules) - 1:
                nxt = self._rules[i + 1]
                r.priority, nxt.priority = nxt.priority, r.priority
                DogfoodRuleRepo.upsert(r)
                DogfoodRuleRepo.upsert(nxt)
                self._reload()
                return

    # ========== 默认行为 ==========

    @Slot(str)
    def setDefaultAction(self, action: str) -> None:
        if action == self._default_action:
            return
        self._default_action = action
        settings.set("dogfood.default_action", action)
        self.defaultActionChanged.emit()

    # ========== 导入导出 ==========

    @Slot(str, result="QVariantMap")
    def exportToFile(self, url: str) -> dict:
        """导出规则到文件，返回 {ok: bool, message: str}"""
        try:
            file_path = self._clean_url(url)
            data = {
                "version": 1,
                "default_action": self._default_action,
                "rules": [r.to_dict() for r in self._rules],
            }
            Path(file_path).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log.info(f"规则已导出: {file_path}")
            return {"ok": True, "message": f"已导出到 {file_path}"}
        except Exception as e:
            log.error(f"导出失败: {e}")
            return {"ok": False, "message": f"导出失败: {e}"}

    @Slot(str, result="QVariantMap")
    def importFromFile(self, url: str) -> dict:
        """从文件导入规则，同名跳过"""
        try:
            file_path = self._clean_url(url)
            data = json.loads(Path(file_path).read_text(encoding="utf-8"))
            imported = [DogfoodRule.from_dict(r) for r in data.get("rules", [])]
            skipped: list[str] = []
            for rule in imported:
                if DogfoodRuleRepo.exists(rule.name):
                    skipped.append(rule.name)
                else:
                    DogfoodRuleRepo.upsert(rule)
            self._default_action = data.get("default_action", self._default_action)
            settings.set("dogfood.default_action", self._default_action)
            self._reload()
            success = len(imported) - len(skipped)
            if skipped:
                log.warning(
                    f"导入完成：成功 {success} 条，跳过 {len(skipped)} 条（同名已存在）"
                )
                return {
                    "ok": True,
                    "message": f"成功导入 {success} 条，跳过 {len(skipped)} 条：{', '.join(skipped)}",
                }
            log.info(f"已导入 {success} 条规则")
            return {"ok": True, "message": f"已导入 {success} 条规则"}
        except Exception as e:
            log.error(f"导入失败: {e}")
            return {"ok": False, "message": f"导入失败: {e}"}

    @Slot("QVariantList", str, result="QVariantMap")
    def exportRules(self, names: list[str], url: str) -> dict:
        """导出选中规则到文件，返回 {ok: bool, message: str}"""
        try:
            file_path = self._clean_url(url)
            name_set = set(names)
            selected = [r for r in self._rules if r.name in name_set]
            if not selected:
                return {"ok": False, "message": "未选中任何规则"}
            data = {
                "version": 1,
                "default_action": self._default_action,
                "rules": [r.to_dict() for r in selected],
            }
            Path(file_path).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log.info(f"已导出 {len(selected)} 条规则到 {file_path}")
            return {"ok": True, "message": f"已导出 {len(selected)} 条规则"}
        except Exception as e:
            log.error(f"导出失败: {e}")
            return {"ok": False, "message": f"导出失败: {e}"}

    @Slot()
    def reload(self) -> None:
        """强制从数据库重新加载规则列表"""
        self._reload()

    @Slot(str, result="QVariantMap")
    def getRule(self, name: str) -> dict:
        """按名称获取单条规则"""
        for r in self._rules:
            if r.name == name:
                return r.to_dict()
        return {}

    # ========== 检测配置 ==========

    @Property("QVariantList", notify=rulesChanged)
    def availableSlotConfigs(self) -> list[dict]:
        """可用检测配置列表，供 QML 下拉选择"""
        return [
            {"name": c.name, "index": i}
            for i, c in enumerate(ALL_SLOT_CONFIGS)
        ]

    @Property(int, notify=rulesChanged)
    def selectedSlotConfigIndex(self) -> int:
        return self._selected_config_index

    @Slot(int)
    def setSelectedSlotConfigIndex(self, index: int) -> None:
        if 0 <= index < len(ALL_SLOT_CONFIGS):
            self._selected_config_index = index

    # ========== 规则测试 ==========

    _TEST_FIELDS: frozenset[ArtifactRecognitionField] = frozenset({
        ArtifactRecognitionField.SET_NAME,
        ArtifactRecognitionField.PIECE_TYPE,
        ArtifactRecognitionField.MAIN_STAT,
        ArtifactRecognitionField.SUB_STATS,
        ArtifactRecognitionField.LEVEL,
        ArtifactRecognitionField.RARITY,
        ArtifactRecognitionField.LOCK_STATUS,
    })

    @Slot()
    def testCurrentArtifact(self) -> None:
        """测试当前选中规则是否匹配游戏中的圣遗物"""
        if not self._selected_name:
            self.statusMessage.emit("请先在规则列表中选择一条规则", 3000, "warning")
            return

        try:
            from backend.automation.ocr_worker import OcrWorker
            from backend.utils.screen_capture import ScreenshotCapture
        except Exception as e:
            log.error(f"导入测试依赖失败: {e}")
            self.statusMessage.emit("测试模块加载失败", 3000, "error")
            return

        config = ALL_SLOT_CONFIGS[self._selected_config_index]
        rule_name = self._selected_name

        # 截图
        self.testStatusChanged.emit("正在截图...")
        capture = ScreenshotCapture()
        result = capture.capture()
        if result is None:
            self.testStatusChanged.emit("截图失败")
            self.statusMessage.emit("截图失败，请确认原神已启动", 3000, "error")
            return

        image = result.image
        roi_configs = dict(config.detail_roi_configs)
        lock_search = config.lock_anchor_search_region
        lock_to_level = config.lock_anchor_to_level
        lock_to_sub = config.lock_anchor_to_sub_stats
        fields = RulePresenter._TEST_FIELDS

        self.testStatusChanged.emit("正在 OCR 识别...")

        worker = OcrWorker.instance()

        def do_recognize(ocr):
            return ArtifactRecognizer.recognize(
                image, roi_configs, ocr,
                fields=fields,
                lock_anchor_search_region=lock_search,
                lock_anchor_to_level=lock_to_level,
                lock_anchor_to_sub_stats=lock_to_sub,
            )

        worker.task_done.connect(self._on_test_ocr_done)
        worker.task_error.connect(self._on_test_ocr_error)
        worker.submit(do_recognize, callback_data=rule_name)

    def _on_test_ocr_done(self, artifact, callback_data: str) -> None:
        """OCR 识别完成 → 规则匹配 → 发射结果"""
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        try:
            worker.task_done.disconnect(self._on_test_ocr_done)
            worker.task_error.disconnect(self._on_test_ocr_error)
        except Exception as e:
            log.debug(f"断开 OCR 信号连接失败: {e}")

        rule_name = callback_data
        self.testStatusChanged.emit("正在匹配规则...")

        # 查找选中规则
        selected_rule = None
        for r in self._rules:
            if r.name == rule_name:
                selected_rule = r
                break

        if selected_rule is None:
            self.testStatusChanged.emit("规则已不存在")
            self.statusMessage.emit("选中的规则已被删除", 3000, "error")
            return

        engine = DogfoodRuleEngine(default_action=self._default_action)
        matched = engine.match(artifact, selected_rule)

        # 所有规则的最终判定
        final_is_dogfood = engine.evaluate(artifact, self._rules)

        # 查询部位图标
        piece_icon = ""
        if artifact.set_id and artifact.piece_type:
            try:
                from database.repository.artifact_piece_repo import ArtifactPieceRepo
                pieces = ArtifactPieceRepo.find_by_set_id(artifact.set_id)
                for p in pieces:
                    if p.type == artifact.piece_type:
                        piece_icon = p.icon
                        break
            except Exception as e:
                log.debug(f"查询部位图标失败: {e}")

        self.testResultReady.emit({
            "ok": True,
            "rule_name": rule_name,
            "rule_action": selected_rule.action,
            "matched": matched,
            "detail": {},
            "final_action": "discard" if final_is_dogfood else "keep",
            "artifact": {
                "set_name": artifact.set_name or "未知",
                "piece_icon": piece_icon,
                "piece_type": artifact.piece_type or "未知",
                "piece_name": artifact.piece_name or "",
                "rarity": artifact.rarity or 0,
                "level": artifact.level or 0,
                "main_stat": (
                    f"{artifact.main_stat.name}+{artifact.main_stat.value}"
                    if artifact.main_stat else "未知"
                ),
                "sub_stats": [
                    {
                        "name": s.name,
                        "value": f"{s.value}{'%' if s.is_percentage else ''}",
                        "activated": s.is_activated,
                    }
                    for s in artifact.sub_stats
                ],
                "is_locked": artifact.is_locked,
                "is_material": artifact.is_material,
                "material_name": artifact.material_name or "",
            },
        })
        self.testStatusChanged.emit("测试完成")

    def _on_test_ocr_error(self, error_msg: str, callback_data: str) -> None:
        """OCR 识别失败"""
        from backend.automation.ocr_worker import OcrWorker

        worker = OcrWorker.instance()
        try:
            worker.task_done.disconnect(self._on_test_ocr_done)
            worker.task_error.disconnect(self._on_test_ocr_error)
        except Exception as e:
            log.debug(f"断开 OCR 信号连接失败(错误回调): {e}")

        log.error(f"规则测试 OCR 失败: {error_msg}")
        self.testStatusChanged.emit("识别失败")
        self.testResultReady.emit({
            "ok": False,
            "error": error_msg,
        })

    @staticmethod
    def _clean_url(url: str) -> str:
        """将 QML file:// URL 转为本地路径"""
        if url.startswith("file:///"):
            return url[8:]
        return url