"""Run metric logging for single-threaded comparison experiments."""

import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class RunSummary:
    run_id: str
    mode: str
    success: bool
    reason: Optional[str]
    csv_path: Path
    json_path: Path
    durations: dict[str, Optional[float]]

    def to_terminal_text(self) -> str:
        lines = [
            "",
            "=" * 60,
            f"[RunSummary] {self.mode} | {self.run_id}",
            f"success: {self.success}",
            f"reason : {self.reason}",
        ]
        for key, value in self.durations.items():
            rendered = "-" if value is None else f"{value:.3f}s"
            lines.append(f"{key:32s}: {rendered}")
        lines.append(f"csv   : {self.csv_path}")
        lines.append(f"json  : {self.json_path}")
        lines.append("=" * 60)
        return "\n".join(lines)


class RunMetricLogger:
    def __init__(self, log_dir: str | Path, mode: str) -> None:
        self.log_dir = Path(log_dir)
        self.mode = mode
        self.run_id = ""
        self._start_perf = 0.0
        self._events: list[dict[str, Any]] = []
        self._marks: dict[str, float] = {}
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start_run(self, camera_index: int) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        self.run_id = now.strftime("%Y%m%d_%H%M%S")
        self._start_perf = time.perf_counter()
        self._events = []
        self._marks = {}
        self._active = True
        self.event("run_started", camera_index=camera_index, wall_time=now.isoformat())

    def mark(self, name: str, **payload: Any) -> None:
        elapsed = self._elapsed()
        self._marks[name] = elapsed
        self.event(name, **payload)

    def mark_once(self, name: str, **payload: Any) -> None:
        if name in self._marks:
            return
        self.mark(name, **payload)

    def event(self, name: str, **payload: Any) -> None:
        if not self._active:
            return
        row = {
            "run_id": self.run_id,
            "mode": self.mode,
            "event": name,
            "elapsed_sec": round(self._elapsed(), 6),
        }
        row.update(payload)
        self._events.append(row)

    def finish(
        self,
        success: bool,
        reason: Optional[str] = None,
        result: Optional[dict] = None,
    ) -> RunSummary:
        if not self._active:
            self.start_run(camera_index=-1)

        self.event("run_finished", success=success, reason=reason)
        durations = self._build_durations()
        csv_path = self.log_dir / f"{self.run_id}_{self.mode}.csv"
        json_path = self.log_dir / f"{self.run_id}_{self.mode}.json"

        self._write_csv(csv_path)
        self._write_json(
            json_path,
            {
                "run_id": self.run_id,
                "mode": self.mode,
                "success": success,
                "reason": reason,
                "durations": durations,
                "result": result,
                "events": self._events,
            },
        )
        self._active = False
        return RunSummary(
            run_id=self.run_id,
            mode=self.mode,
            success=success,
            reason=reason,
            csv_path=csv_path,
            json_path=json_path,
            durations=durations,
        )

    def _elapsed(self) -> float:
        if self._start_perf <= 0:
            return 0.0
        return time.perf_counter() - self._start_perf

    def _build_durations(self) -> dict[str, Optional[float]]:
        return {
            "camera_start_latency": self._diff("camera_start_requested", "camera_started"),
            "face_ready_latency": self._diff("camera_started", "first_face_ready"),
            "measurement_to_capture": self._diff("measurement_requested", "capture_started"),
            "capture_duration": self._diff("capture_started", "capture_finished"),
            "inference_duration": self._diff("inference_started", "inference_finished"),
            "result_latency": self._diff("measurement_requested", "result_ready"),
            "total_run_duration": self._events[-1]["elapsed_sec"] if self._events else None,
            "max_gui_heartbeat_gap": self._max_heartbeat_gap(),
            "max_gui_heartbeat_gap_during_inference": self._max_heartbeat_gap(
                start="inference_started",
                end="inference_finished",
            ),
        }

    def _diff(self, start: str, end: str) -> Optional[float]:
        if start not in self._marks or end not in self._marks:
            return None
        return round(self._marks[end] - self._marks[start], 6)

    def _max_heartbeat_gap(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Optional[float]:
        start_at = self._marks.get(start, float("-inf")) if start else float("-inf")
        end_at = self._marks.get(end, float("inf")) if end else float("inf")
        beats = [
            event["elapsed_sec"]
            for event in self._events
            if event.get("event") == "gui_heartbeat"
            and start_at <= event["elapsed_sec"] <= end_at
        ]
        if len(beats) < 2:
            return None
        return round(max(b - a for a, b in zip(beats, beats[1:])), 6)

    def _write_csv(self, path: Path) -> None:
        keys: list[str] = []
        for event in self._events:
            for key in event:
                if key not in keys:
                    keys.append(key)

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self._events)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
