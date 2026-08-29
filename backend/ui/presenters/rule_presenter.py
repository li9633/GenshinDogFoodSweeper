"""狗粮规则 Presenter"""

from __future__ import annotations

import json
from pathlib import Path

from database.repository.dogfood_rule_repo import DogfoodRuleRepo
from models.dogfood_rule import DogfoodRule
from PySide6.QtCore import Property, QObject, Signal, Slot
from ui.gmessagebox import GMessageBox
from utils.logger import log
from utils.settings_manager import settings

from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
from backend.automation.recognizer import ArtifactRecognizer
from backend.exceptions.automation import GameWindowNotFoundError
from backend.models.artifact_recognition_field import ArtifactRecognitionField
from backend.models.slot_models import ALL_SLOT_CONFIGS


class RulePresenter(QObject):
    rulesChanged = Signal()
    selectedRuleChanged = Signal()
    defaultActionChanged = Signal()
    multiSelectionChanged = Signal()
    statusMessage = Signal(str, int, str)  # msg, duration, level
    testResultReady = Signal("QVariantMap")  # 测试结果
    testStatusChanged = Signal(str)  # 测试状态提示

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rules: list[DogfoodRule] = []
        self._selected_name = ""
        self._multi_selected: set[str] = set()
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
        self._multi_selected.clear()
        self.rulesChanged.emit()
        self.multiSelectionChanged.emit()

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

    # ========== QML 表单辅助 ==========

    @Slot(str, result=str)
    def actionLabel(self, action: str) -> str:
        """将 action 值映射为中文显示标签"""
        return "丢弃" if action == "discard" else "保留"

    @Slot(str, result=str)
    def actionColor(self, action: str) -> str:
        """将 action 值映射为 Theme 颜色键名（danger / success）"""
        return "danger" if action == "discard" else "success"

    @Slot(str, result="QVariantList")
    def getMainStatOptions(self, part: str) -> list[str]:
        """获取指定部位的主词条选项列表"""
        config = self._load_stats_config()
        main_stats = config.get("main_stats_by_piece", {})
        result = ["不限"]
        if part == "*":
            all_stats: list[str] = []
            for stats in main_stats.values():
                for s in stats:
                    if s not in all_stats:
                        all_stats.append(s)
            result.extend(all_stats)
        else:
            result.extend(main_stats.get(part, []))
        return result

    @Slot(str, result="QVariantList")
    def getFilteredSubStats(self, main_stat: str) -> list[str]:
        """获取过滤后的副词条列表（排除与主词条类别冲突的）"""
        config = self._load_stats_config()
        sub_stat_names = config.get("sub_stat_names", [])
        if main_stat in ("*", "不限", ""):
            return sub_stat_names
        stats = config.get("stats", {})
        main_info = stats.get(main_stat, {})
        main_cat = main_info.get("category", "")
        if not main_cat:
            return sub_stat_names
        return [s for s in sub_stat_names if stats.get(s, {}).get("category") != main_cat]

    @Slot(str, str, result=bool)
    def validateMainStatForPart(self, part: str, main_stat: str) -> bool:
        """检查主词条对部位是否合法"""
        if main_stat in ("*", "不限", "", None):
            return True
        config = self._load_stats_config()
        allowed = config.get("main_stats_by_piece", {}).get(part, [])
        return main_stat in allowed

    @Slot("QVariantMap", result="QVariantMap")
    def buildSaveData(self, form_data: dict) -> dict:
        """从表单数据构建保存用的规则数据，将 set_name 转换逻辑从 QML 迁移到 Presenter"""
        selected_sets = form_data.get("selected_sets") or []
        return {
            "name": (form_data.get("name") or "").strip(),
            "_original_name": form_data.get("_original_name", ""),
            "part": form_data.get("part", "*"),
            "part_exclude": form_data.get("part_exclude", ""),
            "main_stat": form_data.get("main_stat", "*"),
            "set_name": "*" if form_data.get("set_enabled", True) else ",".join(selected_sets),
            "sub_stats": form_data.get("sub_stats") or [],
            "sub_count": form_data.get("sub_count", 0),
            "action": form_data.get("action", "keep"),
            "priority": form_data.get("priority", 0),
            "enabled": form_data.get("enabled", True),
            "include_unactivated": form_data.get("include_unactivated", True),
            "include_main_stat": form_data.get("include_main_stat", False),
        }

    @Slot("QVariantMap", result="QVariantMap")
    def buildFormDefaults(self, rule: dict) -> dict:
        """从规则数据构建表单默认值，将数据转换逻辑从 QML 迁移到 Presenter"""
        if not rule or not rule.get("name"):
            return {
                "title": "新建规则",
                "name": "", "part": "*", "part_exclude": "",
                "main_stat": "*", "set_enabled": True,
                "selected_sets": [], "set_search": "",
                "selected_sub_stats": [], "sub_count": 0,
                "action": "keep", "priority": 0, "enabled": True,
                "include_unactivated": True, "include_main_stat": False,
            }

        set_name = rule.get("set_name") or "*"
        selected_sets: list[str] = []
        if set_name not in ("*", ""):
            selected_sets = [s.strip() for s in set_name.split(",") if s.strip()]

        sub_stats = rule.get("sub_stats") or []
        selected_sub_stats = [
            {"name": s.get("name", ""), "op": s.get("op", ""), "value": s.get("value", 0)}
            for s in sub_stats
        ]

        return {
            "title": f"编辑规则 — {rule['name']}",
            "name": rule.get("name", ""),
            "part": rule.get("part") or "*",
            "part_exclude": rule.get("part_exclude") or "",
            "main_stat": rule.get("main_stat") or "*",
            "set_enabled": set_name in ("*", ""),
            "selected_sets": selected_sets,
            "set_search": "",
            "selected_sub_stats": selected_sub_stats,
            "sub_count": rule.get("sub_count") or 0,
            "action": rule.get("action") or "keep",
            "priority": rule.get("priority") or 0,
            "enabled": rule.get("enabled", True),
            "include_unactivated": rule.get("include_unactivated", True),
            "include_main_stat": rule.get("include_main_stat", False),
        }

    # ========== 多选（导出用） ==========

    @Property(int, notify=multiSelectionChanged)
    def multiSelectedCount(self) -> int:
        return len(self._multi_selected)

    @Property("QVariantList", notify=multiSelectionChanged)
    def multiSelectedNames(self) -> list[str]:
        return list(self._multi_selected)

    @Slot(str)
    def toggleMultiSelect(self, name: str) -> None:
        if name in self._multi_selected:
            self._multi_selected.discard(name)
        else:
            self._multi_selected.add(name)
        self.multiSelectionChanged.emit()

    @Slot()
    def clearMultiSelect(self) -> None:
        self._multi_selected.clear()
        self.multiSelectionChanged.emit()

    # ========== CRUD ==========

    @Slot("QVariantMap", result=bool)
    def saveRule(self, rule_map: dict) -> bool:
        """保存规则（新增或更新），名称为主键"""
        try:
            name = rule_map.get("name", "").strip()
            if not name:
                GMessageBox.warning("请输入规则名称")
                return False

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
                return True

            # 编辑模式：名称已变，需检查新名称是否冲突，再删旧存新
            if original_name and original_name != name:
                if DogfoodRuleRepo.exists(name):
                    GMessageBox.warning(f"规则名称「{name}」已存在，请更换名称")
                    return False
                DogfoodRuleRepo.delete(original_name)
                DogfoodRuleRepo.upsert(rule)
                self._reload()
                return True

            # 新建模式：检查名称是否重复
            if DogfoodRuleRepo.exists(name):
                GMessageBox.warning(f"规则名称「{name}」已存在，请更换名称")
                return False
            DogfoodRuleRepo.upsert(rule)
            self._reload()
            return True
        except Exception as e:
            log.error(f"保存规则失败: {e}")
            GMessageBox.error(f"保存失败: {e}")
            return False

    @Slot(str, result=bool)
    def deleteRule(self, name: str) -> bool:
        try:
            DogfoodRuleRepo.delete(name)
            if self._selected_name == name:
                self._selected_name = ""
                self.selectedRuleChanged.emit()
            self._multi_selected.discard(name)
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
        """切换选中：点击已选中则取消，否则选中"""
        if self._selected_name == name:
            self._selected_name = ""
        else:
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
        """导出选中规则到目录，每条规则独立生成 {规则名}.json"""
        try:
            dir_path = self._clean_url(url)
            name_set = set(names)
            selected = [r for r in self._rules if r.name in name_set]
            if not selected:
                return {"ok": False, "message": "未选中任何规则"}
            for rule in selected:
                file_path = Path(dir_path) / f"{rule.name}.json"
                data = {
                    "version": 1,
                    "default_action": self._default_action,
                    "rules": [rule.to_dict()],
                }
                file_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            log.info(f"已导出 {len(selected)} 条规则到 {dir_path}")
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
        try:
            result = capture.capture()
        except GameWindowNotFoundError:
            self.testStatusChanged.emit("截图失败")
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