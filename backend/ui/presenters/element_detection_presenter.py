"""元素检测 Presenter — 模板匹配 + 注册，纯业务逻辑"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
from utils.logger import log

from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


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


class ElementDetectionPresenter:
    """元素检测业务逻辑"""

    # ---------- 模板列表 ----------

    @staticmethod
    def list_templates(keyword: str = "") -> dict[str, str]:
        return (
            TemplateManager.search(keyword) if keyword else TemplateManager.list_all()
        )

    @staticmethod
    def reload_templates() -> None:
        TemplateManager.reload()

    @staticmethod
    def get_template_region(key: str) -> tuple[int, int, int, int] | None:
        return TemplateManager.get_region(key)

    @staticmethod
    def get_template_path(key: str) -> Path | None:
        return TemplateManager.get_path(key)

    # ---------- 条件管理 ----------

    @staticmethod
    def check_duplicate(
        existing_conditions: list[tuple[str, float, tuple | None]], template_key: str
    ) -> bool:
        for cond in existing_conditions:
            if cond[0] == template_key:
                return True
        return False

    # ---------- 检测 ----------

    def detect(
        self,
        conditions: list[tuple[str, float, tuple[int, int, int, int] | None]],
    ) -> DetectionResult:
        t0 = time.perf_counter()
        cap = ScreenshotCapture()
        result = cap.capture()
        full_gray = cv2.cvtColor(result.image, cv2.COLOR_RGB2GRAY)

        all_passed = True
        detail_parts: list[str] = []
        last_matches: list[tuple[str, int, int, int, int]] = []

        for template_key, threshold, region in conditions:
            template_path = TemplateManager.get_path(template_key)
            if template_path is None:
                detail_parts.append(f"{template_key}: 文件不存在")
                all_passed = False
                continue

            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                detail_parts.append(f"{template_key}: 加载失败")
                all_passed = False
                continue

            orig_th, orig_tw = template.shape

            if region:
                rx, ry, rw, rh = region
                search_area = full_gray[ry : ry + rh, rx : rx + rw]
                if search_area.size == 0:
                    detail_parts.append(f"{template_key}: 搜索区域无效")
                    all_passed = False
                    continue
            else:
                rx, ry = 0, 0
                search_area = full_gray

            best_score, best_loc, best_scale, best_size = multi_scale_match(
                search_area, template
            )

            passed = best_score >= threshold
            if not passed:
                all_passed = False

            color = (0, 255, 0) if passed else (255, 0, 0)
            tw, th = best_size
            size_info = (
                f"{tw}x{th}" if best_scale >= 1.0 else f"{tw}x{th}/{orig_tw}x{orig_th}"
            )
            result.draw_rect(
                best_loc[0] + rx,
                best_loc[1] + ry,
                tw,
                th,
                color=color,
                thickness=3,
                label=f"{template_key} {best_score:.2f}",
            )
            detail_parts.append(
                f"{'✓' if passed else '✗'}{template_key}: {best_score:.3f}"
                f"@{best_scale:.2f}x ({size_info}) → ({best_loc[0] + rx},{best_loc[1] + ry})"
            )
            last_matches.append(
                (template_key, best_loc[0] + rx, best_loc[1] + ry, tw, th)
            )

        elapsed = (time.perf_counter() - t0) * 1000
        passed_count = sum(1 for p in detail_parts if p.startswith("✓"))
        total = len(conditions)

        timing = f" ({elapsed:.0f}ms)"
        if all_passed:
            log.info(
                f"全部通过 ({passed_count}/{total}){timing} | "
                + " | ".join(detail_parts)
            )
        else:
            log.warning(
                f"未通过 ({passed_count}/{total}){timing} | " + " | ".join(detail_parts)
            )

        return DetectionResult(
            all_passed=all_passed,
            passed_count=passed_count,
            total=total,
            elapsed_ms=elapsed,
            detail_parts=detail_parts,
            last_matches=last_matches,
            result=result,
        )

    # ---------- 注册 ----------

    @staticmethod
    def register_region(
        selected_key: str,
        last_matches: list[tuple[str, int, int, int, int]],
        display_name: str,
    ) -> tuple[str, int, int, int, int] | None:
        match = next((m for m in last_matches if m[0] == selected_key), None)
        if match is None:
            log.warning(f"[{selected_key}] 本次未匹配成功")
            return None

        _, x, y, w, h = match
        name = display_name if display_name else selected_key

        entry = TemplateManager._find_entry(selected_key)
        filename = (
            str(entry["file"])
            if entry and entry.get("file")
            else f"images/{selected_key}.png"
        )
        TemplateManager.register(name, filename, (x, y, w, h))
        TemplateManager.save()
        log.info(f"[{name}] 区域已注册: ({x},{y},{w}x{h})")
        return name, x, y, w, h
