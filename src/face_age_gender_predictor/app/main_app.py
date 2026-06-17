# main_app.py

import argparse
import os
import random
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Optional

# Windows에서 PyQt5와 torch DLL 로드 순서가 충돌하는 환경을 피한다.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "True")
if "pytest" not in sys.modules:
    try:
        import torch  # noqa: F401
    except Exception as exc:
        print(f"[Single][WARN] torch 사전 로드 실패: {exc}")

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication

from face_age_gender_predictor.camera.camera_detector import CameraDetector, TOTAL_FRAMES
from face_age_gender_predictor.inference.CNNmodel import predict_frames
from face_age_gender_predictor.processing.result_processor import process_predictions
from face_age_gender_predictor.processing.run_metrics import RunMetricLogger


class AppState(Enum):
    IDLE = auto()
    COUNTDOWN = auto()
    CAPTURING = auto()
    ANALYZING = auto()
    DONE = auto()
    ERROR = auto()


class SystemController(QObject):
    """GUI 흐름을 단일 Qt 이벤트 루프에서 처리하는 컨트롤러."""

    status_changed = pyqtSignal(str)
    state_changed = pyqtSignal(str)
    face_ready_changed = pyqtSignal(bool)
    camera_running_changed = pyqtSignal(bool)
    measure_button_enabled_changed = pyqtSignal(bool)
    countdown_changed = pyqtSignal(int)
    capture_progress_changed = pyqtSignal(int, int)
    inference_progress_changed = pyqtSignal(int, int)
    preview_frame_changed = pyqtSignal(object)
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        camera_index: int = 0,
        log_dir: str | Path = "logs/single_thread_runs",
        mock_inference: bool = False,
    ):
        super().__init__()

        self.camera_index = camera_index
        self.state = AppState.IDLE
        self.face_ready = False
        self.camera_running = False
        self.countdown_value = 3
        self.mock_inference = mock_inference

        self.detector: Optional[CameraDetector] = None
        self.metrics = RunMetricLogger(log_dir=log_dir, mode="single_thread")

        self.camera_timer = QTimer(self)
        self.camera_timer.setInterval(33)
        self.camera_timer.timeout.connect(self._poll_camera_once)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)

        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.setInterval(250)
        self.heartbeat_timer.timeout.connect(self._on_gui_heartbeat)

        self._shutting_down = False

    def _set_state(self, new_state: AppState):
        self.state = new_state
        print(f"[Single] 상태 변경 → {self.state.name}")
        self.state_changed.emit(self.state.name)
        self.metrics.event("state_changed", state=self.state.name)
        self._emit_measure_enabled()

    def _emit_measure_enabled(self):
        enabled = self.camera_running and self.face_ready and self.state == AppState.IDLE
        self.measure_button_enabled_changed.emit(enabled)

    def _on_gui_heartbeat(self):
        self.metrics.event("gui_heartbeat", state=self.state.name)

    @pyqtSlot()
    def start_camera(self):
        if self.camera_running:
            self.status_changed.emit("[Single] 카메라가 이미 실행 중입니다.")
            return

        self.metrics.start_run(camera_index=self.camera_index)
        self.metrics.mark("camera_start_requested")
        self.heartbeat_timer.start()

        try:
            self.detector = CameraDetector(camera_index=self.camera_index)
            self.detector.start()
        except Exception as exc:
            self.detector = None
            self.metrics.finish(success=False, reason=str(exc))
            self.on_error(f"카메라 {self.camera_index}를 열 수 없습니다: {exc}")
            return

        self.camera_running = True
        self.camera_running_changed.emit(True)
        self.camera_timer.start()
        self.metrics.mark("camera_started")
        self.status_changed.emit(
            f"[Single] camera_index={self.camera_index} 카메라 시작"
        )
        self._emit_measure_enabled()

    @pyqtSlot()
    def stop_camera(self):
        if self.countdown_timer.isActive():
            self.countdown_timer.stop()
        if self.heartbeat_timer.isActive():
            self.heartbeat_timer.stop()

        self.camera_timer.stop()

        if self.detector is not None:
            self.detector.stop()
            self.detector = None

        self.camera_running = False
        self.face_ready = False
        self._set_state(AppState.IDLE)
        self.camera_running_changed.emit(False)
        self.face_ready_changed.emit(False)
        self.status_changed.emit("[Single] 카메라 종료")

    @pyqtSlot()
    def request_measurement(self):
        if self.state != AppState.IDLE:
            print(f"[Single] 현재 상태가 {self.state.name}이므로 측정 요청을 무시합니다.")
            return

        if not self.camera_running or self.detector is None:
            self.status_changed.emit("[Single] 먼저 카메라를 시작해주세요.")
            return

        if not self.face_ready:
            self.status_changed.emit("[Single] 얼굴이 준비되지 않았습니다.")
            return

        if not self.metrics.is_active:
            self.metrics.start_run(camera_index=self.camera_index)
            self.metrics.mark("camera_start_requested")
            self.metrics.mark("camera_started")
            self.metrics.mark("first_face_ready")
            self.heartbeat_timer.start()

        self.metrics.mark("measurement_requested")
        self._set_state(AppState.COUNTDOWN)
        self.countdown_value = 3
        self.countdown_changed.emit(self.countdown_value)
        self.countdown_timer.start()

    def _on_countdown_tick(self):
        if self.state != AppState.COUNTDOWN:
            self.countdown_timer.stop()
            return

        self.countdown_value -= 1
        if self.countdown_value > 0:
            print(f"[Single] 카운트다운: {self.countdown_value}")
            self.countdown_changed.emit(self.countdown_value)
            return

        self.countdown_timer.stop()
        self.countdown_changed.emit(0)
        self._on_countdown_finished()

    def _on_countdown_finished(self):
        if self.state != AppState.COUNTDOWN or self.detector is None:
            return

        if not self.detector.has_current_face():
            self.on_error("얼굴이 사라져 촬영을 시작할 수 없습니다. 다시 시도해주세요.")
            return

        try:
            self.detector.start_recording()
        except Exception as exc:
            self.on_error(str(exc))
            return

        self.metrics.mark("capture_started")
        self._set_state(AppState.CAPTURING)
        self.capture_progress_changed.emit(0, TOTAL_FRAMES)
        self.status_changed.emit("[Single] 40프레임 촬영 시작")

    def _poll_camera_once(self):
        if not self.camera_running or self.detector is None:
            return

        try:
            state = self.detector.poll_once()
        except Exception as exc:
            self.on_error(str(exc))
            return

        if state.frame is not None:
            self.preview_frame_changed.emit((state.frame, state.face_box))

        if state.face_ready_changed is not None:
            self.face_ready = state.face_ready_changed
            self.face_ready_changed.emit(self.face_ready)
            self.metrics.event("face_ready_changed", ready=self.face_ready)
            if self.face_ready:
                self.metrics.mark_once("first_face_ready")
            self._emit_measure_enabled()

        if state.capture_progress is not None:
            current, total = state.capture_progress
            self.capture_progress_changed.emit(current, total)

        if state.frames_ready is not None:
            self.metrics.mark("capture_finished", frames=len(state.frames_ready))
            self.on_frames_ready(state.frames_ready)

    def on_frames_ready(self, frames):
        if self.state != AppState.CAPTURING:
            print("[Single] 현재 촬영 상태가 아니므로 frames_ready를 무시합니다.")
            return

        print(f"[Single] frames_ready 수신 → {len(frames)}프레임")
        self._set_state(AppState.ANALYZING)
        self._run_inference(frames)

    def _run_inference(self, frames):
        self.metrics.mark("inference_started", frames=len(frames))
        self.status_changed.emit("[Single] 분석 중... GUI 이벤트 루프에서 직접 실행합니다.")

        try:
            if self.mock_inference:
                predictions = self._predict_frames_mock(frames)
            else:
                predictions = predict_frames(
                    frames,
                    progress_callback=lambda current: self.on_inference_progress(
                        current, len(frames)
                    ),
                )

            self.metrics.mark("inference_finished", predictions=len(predictions))
            process_predictions(predictions, on_result_ready=self.on_inference_done)
        except Exception as exc:
            self.metrics.finish(success=False, reason=str(exc))
            self.on_error(str(exc))

    def _predict_frames_mock(self, frames):
        rng = random.Random(20260617)
        predictions = []
        total = len(frames)
        for index, frame in enumerate(frames, start=1):
            _ = frame
            predictions.append(
                {
                    "age": rng.uniform(20, 40),
                    "gender": rng.uniform(0, 1),
                    "age_probs": [1 / 26] * 26,
                    "gender_confidence": rng.uniform(0.7, 1.0),
                }
            )
            self.on_inference_progress(index, total)
        return predictions

    @pyqtSlot(int, int)
    def on_inference_progress(self, current: int, total: int):
        print(f"[Single] 분석 진행률: {current}/{total}")
        self.inference_progress_changed.emit(current, total)

    @pyqtSlot(dict)
    def on_inference_done(self, result: dict):
        self.metrics.mark(
            "result_ready",
            success=bool(result.get("success")),
            valid_count=result.get("valid_count"),
        )

        if result.get("success"):
            self._set_state(AppState.DONE)
            print(
                f"[Single] 최종 결과 → 나이: {result['age']:.1f}세, "
                f"성별: {result['gender']}, "
                f"성별 확신도: {result['gender_confidence'] * 100:.1f}%, "
                f"유효 예측: {result['valid_count']}개"
            )
        else:
            self._set_state(AppState.ERROR)
            print(
                f"[Single] 측정 실패 → reason: {result.get('reason')}, "
                f"유효 예측: {result.get('valid_count')}개"
            )

        self.result_ready.emit(result)
        if self.metrics.is_active:
            summary = self.metrics.finish(
                success=bool(result.get("success")),
                reason=result.get("reason"),
                result=result,
            )
            print(summary.to_terminal_text())
        else:
            print("[Single][WARN] inactive metrics; result was not written to logs")
        self.heartbeat_timer.stop()
        self._return_to_idle()

    @pyqtSlot(str)
    def on_error(self, message: str):
        self._set_state(AppState.ERROR)
        print(f"[Single][ERROR] {message}")
        self.error_occurred.emit(message)
        if self.metrics.is_active:
            summary = self.metrics.finish(success=False, reason=message)
            print(summary.to_terminal_text())
        self.heartbeat_timer.stop()
        self._return_to_idle()

    def _return_to_idle(self):
        if self.countdown_timer.isActive():
            self.countdown_timer.stop()

        self.face_ready = False
        if self.detector is not None:
            self.detector.reset_ready_state()
        self._set_state(AppState.IDLE)
        self.face_ready_changed.emit(False)

    @pyqtSlot()
    def shutdown(self):
        if self._shutting_down:
            return

        self._shutting_down = True
        print("[Single] 종료 요청 수신 → 카메라 정리")
        self.stop_camera()
        print("[Single] 정리 완료")


def connect_window_and_controller(window, controller: SystemController) -> None:
    window.start_camera_requested.connect(controller.start_camera)
    window.measurement_requested.connect(controller.request_measurement)
    window.stop_camera_requested.connect(controller.stop_camera)
    window.close_requested.connect(controller.shutdown)

    controller.status_changed.connect(window.on_status_message)
    controller.state_changed.connect(window.on_state_changed)
    controller.face_ready_changed.connect(window.on_face_ready_changed)
    controller.camera_running_changed.connect(window.on_camera_running_changed)
    controller.measure_button_enabled_changed.connect(window.on_measure_enabled_changed)
    controller.countdown_changed.connect(window.on_countdown_changed)
    controller.capture_progress_changed.connect(window.on_capture_progress)
    controller.inference_progress_changed.connect(window.on_inference_progress)
    controller.preview_frame_changed.connect(window.on_preview_frame)
    controller.result_ready.connect(window.on_result_ready)
    controller.error_occurred.connect(window.on_error_message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the single-threaded GUI app.")
    parser.add_argument(
        "--camera-index",
        "-c",
        type=int,
        default=0,
        help="OpenCV camera index. Try 1 or 2 for DroidCam.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs/single_thread_runs",
        help="Directory where CSV/JSON run metrics are saved.",
    )
    parser.add_argument(
        "--mock-inference",
        action="store_true",
        help="Use deterministic lightweight predictions instead of the .pt model.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    args = parse_args(argv)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")

    from face_age_gender_predictor.app.main_window import AgeEstimatorWindow

    controller = SystemController(
        camera_index=args.camera_index,
        log_dir=args.log_dir,
        mock_inference=args.mock_inference,
    )
    window = AgeEstimatorWindow()

    connect_window_and_controller(window, controller)

    app.aboutToQuit.connect(controller.shutdown)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv[1:])
