"""元素检测 Presenter — QObject 封装，供 QML 绑定

模板列表查询、检测条件管理、多尺度模板匹配、区域注册。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.logger import log

from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture

from .image_provider import PreviewImageProvider


@dataclass
class DetectionResult:
    """一次检测的完整结果"""

    all_passed: bool
    passed_count: int
    total: int
    elapsed_ms: float
    detail_parts: list[str]
    last_matches: list[tuple[str, int, int, int, int]]
    result: CaptureResult


@dataclass
class TemplateInfo:
    """模板信息 DTO"""
    name: str
    fileName: str
    displayText: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "fileName": self.fileName,
            "displayText": self.displayText,
        }


@dataclass
class Condition:
    """检测条件 DTO"""
    key: str
    templateName: str
    fileName: str
    threshold: float
    thresholdText: str
    rx: int
    ry: int
    rw: int
    rh: int
    regionText: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "templateName": self.templateName,
            "fileName": self.fileName,
            "threshold": self.threshold,
            "thresholdText": self.thresholdText,
            "rx": self.rx,
            "ry": self.ry,
            "rw": self.rw,
            "rh": self.rh,
            "regionText": self.regionText,
        }


class ElementDetectionPresenter(QObject):
    """元素检测 Presenter — QML 可绑定"""

    # -- 信号 --
    templatesChanged = Signal()
    conditionsChanged = Signal()
    templateSelected = Signal(str, str, int, int, int, int, bool)
    # key, previewPath, rx, ry, rw, rh, hasRegion
    detectionFinished = Signal(bool, str, str)
    # allPassed, detailText, resultImagePath
    regionRegistered = Signal(str, int, int, int, int)
    # name, x, y, w, h
    errorOccurred = Signal(str)
    detectingChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._template_list: list[TemplateInfo] = []
        self._template_file_map: dict[str, str] = {}
        self._conditions: list[Condition] = []
        self._last_matches: list[tuple[str, int, int, int, int]] = []
        self._detecting: bool = False
        self._refresh_templates()

    # ========== 模板列表 ==========

    def _refresh_templates(self, keyword: str = "") -> None:
        d = TemplateManager.search(keyword) if keyword else TemplateManager.list_all()
        self._template_list = [
            TemplateInfo(name=name, fileName=Path(path).name, displayText=f"{name}({Path(path).name})")
            for name, path in d.items()
        ]
        self._template_file_map = {name: Path(path).name for name, path in d.items()}
        self.templatesChanged.emit()

    @Property(list, notify=templatesChanged)
    def templateList(self) -> list[dict]:
        return [t.to_dict() for t in self._template_list]

    @Property("QStringList", notify=templatesChanged)
    def templateNames(self) -> list[str]:
        return [t.name for t in self._template_list]

    def getTemplateFileName(self, name: str) -> str:
        return self._template_file_map.get(name, name + ".png")

    @Slot(str)
    def searchTemplates(self, keyword: str) -> None:
        self._refresh_templates(keyword.strip())

    @Slot()
    def reloadTemplates(self) -> None:
        TemplateManager.reload()
        self._refresh_templates()

    @Slot(str)
    def selectTemplate(self, key: str) -> None:
        """用户选中模板 → 加载预览图 + 区域信息"""
        template = TemplateManager.get(key)
        preview_path = str(template.path) if template else ""
        if template and template.region:
            rx, ry, rw, rh = template.region
            self.templateSelected.emit(key, preview_path, rx, ry, rw, rh, True)
        else:
            self.templateSelected.emit(key, preview_path, 0, 0, 0, 0, False)

    # ========== 条件管理 ==========

    @Property(list, notify=conditionsChanged)
    def conditions(self) -> list[dict]:
        return [c.to_dict() for c in self._conditions]

    @Slot(str, float, int, int, int, int)
    def addCondition(
        self, key: str, threshold: float, rx: int, ry: int, rw: int, rh: int
    ) -> None:
        for c in self._conditions:
            if c.key == key:
                self.errorOccurred.emit(f"模板 '{key}' 已存在")
                return
        has_region = rw > 0 and rh > 0
        self._conditions.append(Condition(
            key=key,
            templateName=key,
            fileName=self._template_file_map.get(key, key + ".png"),
            threshold=threshold,
            thresholdText=f"{int(threshold * 100)}%",
            rx=rx,
            ry=ry,
            rw=rw,
            rh=rh,
            regionText=f"区域:({rx},{ry},{rw}x{rh})" if has_region else "全屏",
        ))
        self.conditionsChanged.emit()

    @Slot(int, int, bool, int, int, int, int)
    def addConditionByIndex(
        self, index: int, threshold_percent: int,
        has_region: bool, rx: int, ry: int, rw: int, rh: int
    ) -> None:
        if index < 0 or index >= len(self._template_list):
            self.errorOccurred.emit("无效模板索引")
            return
        item = self._template_list[index]
        th = threshold_percent / 100.0
        region_x = rx if has_region else 0
        region_y = ry if has_region else 0
        region_w = rw if has_region else 0
        region_h = rh if has_region else 0
        self.addCondition(item.name, th, region_x, region_y, region_w, region_h)

    @Slot(int)
    def removeCondition(self, index: int) -> None:
        if 0 <= index < len(self._conditions):
            self._conditions.pop(index)
            self.conditionsChanged.emit()

    @Slot()
    def clearConditions(self) -> None:
        self._conditions.clear()
        self._last_matches.clear()
        self.conditionsChanged.emit()

    @Property(int, notify=conditionsChanged)
    def conditionCount(self) -> int:
        return len(self._conditions)

    @Property(bool, notify=detectingChanged)
    def detecting(self) -> bool:
        return self._detecting

    # ========== 检测 ==========

    @Slot()
    def detect(self) -> None:
        if not self._conditions:
            self.errorOccurred.emit("请先添加检测条件")
            return

        self._detecting = True
        self.detectingChanged.emit()

        try:
            conds: list[tuple[str, float, tuple | None]] = []
            for c in self._conditions:
                region = (
                    (c.rx, c.ry, c.rw, c.rh)
                    if c.rw > 0 and c.rh > 0
                    else None
                )
                conds.append((c.key, c.threshold, region))

            t0 = time.perf_counter()
            cap = ScreenshotCapture()
            result = cap.capture()

            all_passed = True
            detail_parts: list[str] = []
            last_matches: list[tuple[str, int, int, int, int]] = []

            for template_key, threshold, region in conds:
                template = TemplateManager.get(template_key)
                if template is None:
                    detail_parts.append(f"✗ {template_key}: 文件不存在")
                    all_passed = False
                    continue

                best_score, (cx, cy), best_scale, (tw, th) = multi_scale_match(
                    result.image,
                    template,
                    use_region=(region is not None),
                    search_region=region,
                )

                passed = best_score >= threshold
                if not passed:
                    all_passed = False

                lx = cx - tw // 2
                ly = cy - th // 2

                color = (0, 255, 0) if passed else (255, 0, 0)
                result.draw_rect(
                    lx, ly, tw, th,
                    color=color,
                    thickness=3,
                    label=f"{template_key} {best_score:.2f}",
                )
                detail_parts.append(
                    f"{'✓' if passed else '✗'} {template_key}: {best_score:.3f}"
                    f"@{best_scale:.2f}x ({tw}x{th})"
                )
                last_matches.append((template_key, lx, ly, tw, th))

            elapsed = (time.perf_counter() - t0) * 1000
            passed_count = sum(1 for p in detail_parts if p.startswith("✓"))
            total = len(conds)

            self._last_matches = last_matches

            key = PreviewImageProvider.put("detection", result.image)

            summary = f"{'✓ 全部通过' if all_passed else '✗ 未通过'} ({passed_count}/{total}, {elapsed:.0f}ms)"
            detail_text = summary + "\n" + "\n".join(detail_parts)

            if all_passed:
                log.info(summary + " | " + " | ".join(detail_parts))
            else:
                log.warning(summary + " | " + " | ".join(detail_parts))

            self.detectionFinished.emit(all_passed, detail_text, key)

        finally:
            self._detecting = False
            self.detectingChanged.emit()

    # ========== 注册 ==========

    @Slot(str, str)
    def registerRegion(self, selected_key: str, display_name: str) -> None:
        """将最近一次匹配结果注册为模板区域"""
        match = next(
            (m for m in self._last_matches if m[0] == selected_key), None
        )
        if match is None:
            self.errorOccurred.emit(f"[{selected_key}] 本次未匹配成功")
            return

        _, x, y, w, h = match
        name = display_name.strip() if display_name.strip() else selected_key

        entry = TemplateManager._find_entry(selected_key)
        filename = (
            str(entry["file"])
            if entry and entry.get("file")
            else f"images/{selected_key}.png"
        )
        TemplateManager.register(name, filename, (x, y, w, h))
        TemplateManager.save()
        log.debug(f"[{name}] 区域已注册: ({x},{y},{w}x{h})")
        self.regionRegistered.emit(name, x, y, w, h)

    @Slot(int, str)
    def registerRegionByIndex(self, index: int, display_name: str) -> None:
        """通过条件列表索引注册区域"""
        if index < 0 or index >= len(self._conditions):
            self.errorOccurred.emit("无效条件索引")
            return
        self.registerRegion(self._conditions[index].key, display_name)