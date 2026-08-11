"""数据同步 Worker — 后台线程执行圣遗物数据同步"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class SyncWorker(QThread):
    """后台线程：执行圣遗物数据同步"""

    finished_sync = pyqtSignal(int, int, int)
    progress = pyqtSignal(int, int, str)
    failed = pyqtSignal(str)

    def run(self) -> None:
        from crawler.artifact_set_fetcher import ArtifactSetFetcher

        try:
            data = ArtifactSetFetcher.run_concurrent(
                progress_callback=self.progress.emit
            )
            total_slots = sum(len(item.get("slots", [])) for item in data)
            total_expected = 0
            for item in data:
                effects = item.get("set_effects", {})
                if "1pc" in effects and "2pc" not in effects and "4pc" not in effects:
                    total_expected += 1
                else:
                    total_expected += 5
            self.finished_sync.emit(len(data), total_slots, total_expected)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
