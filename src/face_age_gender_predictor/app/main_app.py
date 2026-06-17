# main_app.py

import os  # 런타임 환경 변수를 설정하기 위해 사용
import sys  # 프로그램 실행/종료 인자를 다루기 위해 사용
import argparse
from enum import Enum, auto  # 상태 Enum을 만들기 위해 사용
from pathlib import Path

# Windows에서 PyQt5를 먼저 로드한 뒤 torch를 지연 import하면 torch c10.dll 초기화가
# 실패하는 환경이 있다. 모델 파일 로드/추론은 여전히 InferenceWorker에서 수행하지만,
# torch DLL 자체는 Qt보다 먼저 올려 DLL 로드 순서 충돌을 피한다.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "True")
if "pytest" not in sys.modules:
    try:
        import torch  # noqa: F401
    except Exception as exc:
        print(f"[Sys][WARN] torch 사전 로드 실패: {exc}")

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QTimer  # PyQt 핵심 클래스 import
from PyQt5.QtWidgets import QApplication  # GUI 앱 진입점을 위해 import
from PyQt5.QtCore import Qt  # High DPI 속성 설정을 위해 import

from face_age_gender_predictor.app.workers import (
    CameraBridgeWorker,
    InferenceWorker,
)  # Worker 클래스들 import
from face_age_gender_predictor.processing.run_metrics import RunMetricLogger


class AppState(Enum):
    """프로그램 내부 상태 정의"""

    IDLE = auto()  # 대기 상태
    COUNTDOWN = auto()  # 카운트다운 상태
    CAPTURING = auto()  # 40프레임 촬영 상태
    ANALYZING = auto()  # 추론/후처리 상태
    DONE = auto()  # 성공 완료 상태
    ERROR = auto()  # 오류 상태


class SystemController(QObject):
    """GUI와 Worker(QThread) 사이의 흐름을 중재하는 컨트롤러.

    GUI는 버튼 입력을 signal로 보내고, 카메라/추론은 WorkerThread에서 실행된다.
    컨트롤러는 화면을 직접 그리지 않고 상태 전이와 signal 중계만 담당한다.
    """

    # --- CameraWorker로 보내는 요청 signal ---
    start_capture_requested = pyqtSignal()  # CameraWorker에 40프레임 촬영을 요청
    resume_detection_requested = pyqtSignal()  # CameraWorker에 감지 재개를 요청
    stop_camera_requested = pyqtSignal()  # CameraWorker에 카메라 종료를 요청

    # --- GUI로 보내는 상태/결과 signal ---
    status_changed = pyqtSignal(str)  # 상태 메시지
    state_changed = pyqtSignal(str)  # AppState 이름
    face_ready_changed = pyqtSignal(bool)  # 얼굴 준비 여부
    camera_running_changed = pyqtSignal(bool)  # 카메라 실행 여부
    measure_button_enabled_changed = pyqtSignal(bool)  # 측정 버튼 활성화 여부
    countdown_changed = pyqtSignal(int)  # 카운트다운 값 (0이면 종료)
    capture_progress_changed = pyqtSignal(int, int)  # 캡처 진행률 (current, total)
    inference_progress_changed = pyqtSignal(int, int)  # 추론 진행률 (current, total)
    preview_frame_changed = pyqtSignal(object)  # (frame, face_box) 미리보기 프레임
    result_ready = pyqtSignal(dict)  # 최종 result dict (success/failure 모두)
    error_occurred = pyqtSignal(str)  # 오류 메시지

    def __init__(
        self,
        camera_index: int = 0,
        log_dir: str | Path = "logs/threaded_runs",
    ):  # 생성자
        super().__init__()  # QObject 초기화

        self.camera_index = camera_index  # 사용할 카메라 번호
        self.state = AppState.IDLE  # 초기 상태는 IDLE
        self.face_ready = False  # 얼굴 준비 여부 초기값
        self.camera_running = False  # 카메라 실행 여부 초기값
        self.countdown_value = 3  # 카운트다운 시작 숫자

        self.camera_thread = None  # 카메라 QThread 저장 공간
        self.camera_worker = None  # 카메라 Worker 저장 공간

        self.inference_thread = None  # 추론 QThread 저장 공간
        self.inference_worker = None  # 추론 Worker 저장 공간

        self.countdown_timer = QTimer(self)  # 카운트다운용 타이머 생성
        self.countdown_timer.setInterval(1000)  # 1초마다 timeout 발생
        self.countdown_timer.timeout.connect(self._on_countdown_tick)  # countdown 처리 함수 연결

        self.metrics = RunMetricLogger(log_dir=log_dir, mode="threaded")
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.setInterval(250)
        self.heartbeat_timer.timeout.connect(self._on_gui_heartbeat)

        self._shutting_down = False  # 종료 중복 호출 방지 플래그

    # ===== 상태 관리 =====

    def _set_state(self, new_state: AppState):  # 상태 변경 함수
        self.state = new_state  # 새 상태 저장
        print(f"[Sys] 상태 변경 → {self.state.name}")  # 상태 변경 출력
        self.state_changed.emit(self.state.name)  # GUI에 상태 이름 전달
        self.metrics.event("state_changed", state=self.state.name)
        self._emit_measure_enabled()  # 상태에 따른 측정 버튼 활성화 갱신

    def _on_gui_heartbeat(self):
        self.metrics.event("gui_heartbeat", state=self.state.name)

    def _is_busy(self) -> bool:  # 측정 진행 중인지 여부
        return self.state in {
            AppState.COUNTDOWN,
            AppState.CAPTURING,
            AppState.ANALYZING,
        }

    def _emit_measure_enabled(self):  # 측정 버튼 활성화 조건 계산 후 emit
        enabled = self.camera_running and self.face_ready and self.state == AppState.IDLE
        self.measure_button_enabled_changed.emit(enabled)

    # ===== 카메라 WorkerThread =====

    @pyqtSlot()
    def start_camera(self):  # GUI 카메라 시작 버튼 → 카메라 WorkerThread 시작
        if self.camera_thread is not None:  # 이미 카메라가 실행 중이면
            print("[Sys] 카메라가 이미 실행 중입니다.")  # 안내 출력
            return  # 함수 종료

        self.metrics.start_run(camera_index=self.camera_index)
        self.metrics.mark("camera_start_requested")
        self.heartbeat_timer.start()

        self.camera_thread = QThread()  # 카메라용 QThread 생성
        self.camera_worker = CameraBridgeWorker(camera_index=self.camera_index)  # 카메라 Worker 생성

        self.camera_worker.moveToThread(self.camera_thread)  # Worker를 카메라 Thread로 이동

        self.camera_thread.started.connect(self.camera_worker.start_camera)  # Thread 시작 시 카메라 시작
        self.camera_worker.started.connect(self._on_camera_started)  # 카메라 시작 성공 시 상태 갱신
        self.camera_worker.status_changed.connect(self.on_status_changed)  # 카메라 상태 메시지 연결
        self.camera_worker.face_ready_changed.connect(self.on_face_ready_changed)  # 얼굴 준비 signal 연결
        self.camera_worker.preview_frame_ready.connect(self.on_preview_frame)  # 미리보기 프레임 연결
        self.camera_worker.capture_progress.connect(self.on_capture_progress)  # 캡처 진행률 연결
        self.camera_worker.frames_ready.connect(self.on_frames_ready)  # 40프레임 완료 signal 연결
        self.camera_worker.error_occurred.connect(self.on_error)  # 카메라 오류 signal 연결

        self.start_capture_requested.connect(self.camera_worker.start_capture)  # 촬영 요청 연결
        self.resume_detection_requested.connect(self.camera_worker.resume_detection)  # 감지 재개 요청 연결
        self.stop_camera_requested.connect(self.camera_worker.stop_camera)  # 종료 요청 연결

        self.camera_worker.finished.connect(self.camera_thread.quit)  # Worker 종료 시 Thread 종료
        self.camera_worker.finished.connect(self.camera_worker.deleteLater)  # Worker 객체 정리
        self.camera_thread.finished.connect(self.camera_thread.deleteLater)  # Thread 객체 정리
        self.camera_thread.finished.connect(self._clear_camera_refs)  # 카메라 참조 정리

        # 카메라 실행 상태는 Worker가 실제 시작에 성공한 뒤(_on_camera_started)에만 True로 만든다.
        # 카메라 열기 실패 시에는 Worker가 error_occurred + finished를 emit하므로
        # camera_running이 True로 남지 않고 _clear_camera_refs에서 정리된다.
        self.camera_thread.start()  # 카메라 Thread 시작

    @pyqtSlot()
    def _on_camera_started(self):  # 카메라가 실제로 시작된 뒤 호출
        self.camera_running = True  # 카메라 실행 상태 갱신
        self.camera_running_changed.emit(True)  # GUI에 카메라 실행 알림
        self.metrics.mark("camera_started")
        self._emit_measure_enabled()  # 측정 버튼 상태 갱신

    @pyqtSlot()
    def stop_camera(self):  # GUI 카메라 종료 버튼 → 카메라 WorkerThread 정지
        if self.camera_thread is None:  # 카메라가 없으면
            return  # 함수 종료

        if self.countdown_timer.isActive():  # 카운트다운 중이면
            self.countdown_timer.stop()  # 타이머 정지

        self.stop_camera_requested.emit()  # CameraWorker에 종료 요청

        self.camera_running = False  # 카메라 실행 상태 갱신
        self.face_ready = False  # 얼굴 준비 상태 초기화
        self._set_state(AppState.IDLE)  # 상태를 IDLE로 복귀
        self.camera_running_changed.emit(False)  # GUI에 카메라 종료 알림
        self.face_ready_changed.emit(False)  # 얼굴 준비 해제 알림

    @pyqtSlot()
    def _clear_camera_refs(self):  # 카메라 Worker/Thread 참조 정리
        self.camera_thread = None  # 카메라 Thread 참조 제거
        self.camera_worker = None  # 카메라 Worker 참조 제거

        # 카메라 시작 실패 등으로 Thread가 정리됐는데 실행 중 상태가 남아 있으면
        # UI가 "카메라 실행 중"으로 잘못 고정되지 않도록 상태를 복구한다.
        if self.camera_running:
            self.camera_running = False  # 카메라 실행 상태 해제
            self.face_ready = False  # 얼굴 준비 상태 초기화
            self.camera_running_changed.emit(False)  # GUI에 카메라 종료 알림
            self._emit_measure_enabled()  # 측정 버튼 상태 갱신

    # ===== 카메라 → 컨트롤러 콜백 =====

    @pyqtSlot(str)
    def on_status_changed(self, message: str):  # 카메라 상태 메시지 수신
        print(message)  # 콘솔 출력
        self.status_changed.emit(message)  # GUI로 전달

    @pyqtSlot(bool)
    def on_face_ready_changed(self, ready: bool):  # 얼굴 준비 상태 수신
        self.face_ready = ready  # 얼굴 준비 상태 저장

        if ready:  # 얼굴이 준비되었으면
            print("[Sys] 얼굴 감지됨 → 측정 준비 완료")  # 준비 완료 출력
            self.metrics.mark_once("first_face_ready")
        else:  # 얼굴이 준비되지 않았으면
            print("[Sys] 얼굴 미감지 → 측정 불가")  # 준비 해제 출력

        self.metrics.event("face_ready_changed", ready=ready)

        self.face_ready_changed.emit(ready)  # GUI로 전달
        self._emit_measure_enabled()  # 측정 버튼 상태 갱신

    @pyqtSlot(object)
    def on_preview_frame(self, payload):  # (frame, face_box) 미리보기 수신
        self.preview_frame_changed.emit(payload)  # GUI로 그대로 전달

    @pyqtSlot(int, int)
    def on_capture_progress(self, current: int, total: int):  # 캡처 진행률 수신
        self.capture_progress_changed.emit(current, total)  # GUI로 전달

    # ===== 측정 흐름 =====

    @pyqtSlot()
    def request_measurement(self):  # GUI 측정 버튼 → 측정 요청
        if self.state != AppState.IDLE:  # IDLE 상태가 아니면 (중복 요청 방지)
            print(f"[Sys] 현재 상태가 {self.state.name}이므로 측정 요청을 무시합니다.")  # 무시 메시지
            return  # 함수 종료

        if not self.camera_running:  # 카메라가 꺼져 있으면
            self.status_changed.emit("[Sys] 먼저 카메라를 시작해주세요.")  # 안내
            return  # 함수 종료

        if not self.face_ready:  # 얼굴 준비가 안 되었으면
            self.status_changed.emit("[Sys] 얼굴이 준비되지 않았습니다.")  # 안내
            return  # 함수 종료

        if not self.metrics.is_active:
            self.metrics.start_run(camera_index=self.camera_index)
            self.metrics.mark("camera_start_requested")
            self.metrics.mark("camera_started")
            self.metrics.mark("first_face_ready")
            self.heartbeat_timer.start()

        self.metrics.mark("measurement_requested")
        self._set_state(AppState.COUNTDOWN)  # 상태를 COUNTDOWN으로 변경 (측정 버튼 비활성화)
        self.countdown_value = 3  # 카운트다운 값을 3으로 초기화
        self.countdown_changed.emit(self.countdown_value)  # 첫 숫자를 GUI에 전달
        self.countdown_timer.start()  # 카운트다운 타이머 시작

    def _on_countdown_tick(self):  # 카운트다운 tick 처리
        if self.state != AppState.COUNTDOWN:  # COUNTDOWN 상태가 아니면
            self.countdown_timer.stop()  # 타이머 정지
            return  # 함수 종료

        self.countdown_value -= 1  # 숫자 1 감소

        if self.countdown_value > 0:  # 아직 숫자가 남아 있으면
            print(f"[Sys] 카운트다운: {self.countdown_value}")  # 현재 숫자 출력
            self.countdown_changed.emit(self.countdown_value)  # GUI에 전달
            return  # 다음 tick 대기

        self.countdown_timer.stop()  # 카운트다운 종료 후 타이머 정지
        self.countdown_changed.emit(0)  # GUI에 종료 알림
        self._on_countdown_finished()  # 카운트다운 완료 처리

    def _on_countdown_finished(self):  # 카운트다운 완료 처리
        if self.state != AppState.COUNTDOWN:  # COUNTDOWN 상태가 아니면
            print("[Sys] 잘못된 상태의 countdown_finished 신호를 무시합니다.")  # 방어 메시지
            return  # 함수 종료

        # 카운트다운 종료 시점 얼굴 상태 재검증
        if not self.face_ready:  # 얼굴이 사라졌으면
            print("[Sys] 카운트다운 종료 시점에 얼굴이 없습니다 → 촬영 취소")  # 안내
            self.on_error("얼굴이 사라져 촬영을 시작할 수 없습니다. 다시 시도해주세요.")  # 오류 흐름
            return  # 함수 종료

        self._set_state(AppState.CAPTURING)  # 상태를 CAPTURING으로 변경
        print("[Sys] CameraWorker에 40프레임 촬영 요청")  # 촬영 요청 메시지
        self.metrics.mark("capture_started")
        self.start_capture_requested.emit()  # CameraWorker에 촬영 요청 (CameraThread에서 실행)

    @pyqtSlot(object)
    def on_frames_ready(self, frames):  # 40프레임 수신
        if self.state != AppState.CAPTURING:  # CAPTURING 상태가 아니면
            print("[Sys] 현재 촬영 상태가 아니므로 frames_ready를 무시합니다.")  # 방어 메시지
            return  # 함수 종료

        print(f"[Sys] frames_ready 수신 → {len(frames)}프레임")  # 프레임 수 출력
        self.metrics.mark("capture_finished", frames=len(frames))
        self._set_state(AppState.ANALYZING)  # 상태를 ANALYZING으로 변경
        self._start_inference_worker(frames)  # 추론 WorkerThread 시작

    # ===== 추론 WorkerThread =====

    def _start_inference_worker(self, frames):  # 추론 WorkerThread 시작
        if self.inference_thread is not None:  # 이미 추론 중이면 (중복 추론 방지)
            print("[Sys] 이미 추론이 진행 중입니다.")  # 안내
            return  # 함수 종료

        self.inference_thread = QThread()  # 추론용 QThread 생성
        self.inference_worker = InferenceWorker(frames)  # frames를 가진 추론 Worker 생성
        self.metrics.mark("inference_started", frames=len(frames))

        self.inference_worker.moveToThread(self.inference_thread)  # Worker를 추론 Thread로 이동

        self.inference_thread.started.connect(self.inference_worker.run)  # Thread 시작 시 추론 실행
        self.inference_worker.progress_changed.connect(self.on_inference_progress)  # 진행률 연결
        self.inference_worker.result_ready.connect(self.on_inference_done)  # 결과 연결
        self.inference_worker.error_occurred.connect(self.on_error)  # 오류 연결

        self.inference_worker.finished.connect(self.inference_thread.quit)  # Worker 종료 시 Thread 종료
        self.inference_worker.finished.connect(self.inference_worker.deleteLater)  # Worker 정리
        self.inference_thread.finished.connect(self.inference_thread.deleteLater)  # Thread 정리
        self.inference_thread.finished.connect(self._clear_inference_refs)  # 추론 참조 정리

        self.inference_thread.start()  # 추론 Thread 시작

    @pyqtSlot(int, int)
    def on_inference_progress(self, current: int, total: int):  # 추론 진행률 수신
        print(f"[Sys] 분석 진행률: {current}/{total}")  # 진행률 출력
        self.inference_progress_changed.emit(current, total)  # GUI로 전달

    @pyqtSlot(dict)
    def on_inference_done(self, result: dict):  # 추론 완료 (성공/실패 result dict)
        self.metrics.mark(
            "inference_finished",
            success=bool(result.get("success")),
            valid_count=result.get("valid_count"),
        )
        if result.get("success"):  # 성공 result면
            self._set_state(AppState.DONE)  # 상태를 DONE으로 변경
            print(
                f"[Sys] 최종 결과 → "
                f"나이: {result['age']:.1f}세, "
                f"성별: {result['gender']}, "
                f"성별 확신도: {result['gender_confidence'] * 100:.1f}%, "
                f"유효 예측: {result['valid_count']}개"
            )
        else:  # 실패 result면
            self._set_state(AppState.ERROR)  # 상태를 ERROR로 변경
            print(
                f"[Sys] 측정 실패 → reason: {result.get('reason')}, "
                f"유효 예측: {result.get('valid_count')}개"
            )

        self.result_ready.emit(result)  # GUI로 성공/실패 result 전달
        self.metrics.mark(
            "result_ready",
            success=bool(result.get("success")),
            valid_count=result.get("valid_count"),
        )
        summary = self.metrics.finish(
            success=bool(result.get("success")),
            reason=result.get("reason"),
            result=result,
        )
        print(summary.to_terminal_text())
        self.heartbeat_timer.stop()
        self._return_to_idle()  # 재측정 가능한 IDLE 상태로 복귀

    @pyqtSlot()
    def _clear_inference_refs(self):  # 추론 Worker/Thread 참조 정리
        self.inference_thread = None  # 추론 Thread 참조 제거
        self.inference_worker = None  # 추론 Worker 참조 제거

    # ===== 오류/복구 =====

    @pyqtSlot(str)
    def on_error(self, message: str):  # 오류 처리
        self._set_state(AppState.ERROR)  # 상태를 ERROR로 변경
        print(f"[Sys][ERROR] {message}")  # 오류 메시지 출력
        self.error_occurred.emit(message)  # GUI로 오류 전달
        if self.metrics.is_active:
            summary = self.metrics.finish(success=False, reason=message)
            print(summary.to_terminal_text())
        self.heartbeat_timer.stop()
        self._return_to_idle()  # 복구 가능한 IDLE 상태로 복귀

    def _return_to_idle(self):  # 성공/실패 후 재측정 가능한 상태로 복귀
        if self.countdown_timer.isActive():  # 카운트다운이 남아 있으면
            self.countdown_timer.stop()  # 정지

        self.face_ready = False  # 다음 측정을 위해 준비 상태 초기화
        self._set_state(AppState.IDLE)  # IDLE 상태로 복귀
        self.face_ready_changed.emit(False)  # GUI에 준비 해제 알림

        if self.camera_running:  # 카메라가 켜져 있으면
            self.resume_detection_requested.emit()  # 카메라 감지 재개 요청

    # ===== 종료 정리 =====

    @pyqtSlot()
    def shutdown(self):  # 프로그램 종료 처리 (카메라/QThread 정리)
        if self._shutting_down:  # 이미 종료 중이면
            return  # 중복 종료 방지

        self._shutting_down = True  # 종료 중 플래그 설정
        print("[Sys] 종료 요청 수신 → 카메라/스레드 정리")  # 종료 메시지 출력

        if self.countdown_timer.isActive():  # 카운트다운 타이머가 켜져 있으면
            self.countdown_timer.stop()  # 타이머 정지

        if self.heartbeat_timer.isActive():
            self.heartbeat_timer.stop()

        # 추론 Thread 정리
        if self.inference_thread is not None:  # 추론이 진행 중이면
            self.inference_thread.quit()  # 추론 Thread 종료 요청
            self.inference_thread.wait(3000)  # 최대 3초 대기

        # 카메라 Thread 정리
        if self.camera_thread is not None:  # 카메라가 실행 중이면
            self.stop_camera_requested.emit()  # 카메라 종료 요청 (CameraThread에서 처리)
            self.camera_thread.quit()  # 카메라 Thread 종료 요청
            self.camera_thread.wait(3000)  # 최대 3초 대기

        self.camera_running = False  # 카메라 실행 상태 해제
        print("[Sys] 정리 완료")  # 정리 완료 출력


def connect_window_and_controller(window, controller: SystemController) -> None:
    """GUI(window)와 SystemController를 signal/slot으로 연결한다."""

    # GUI → Controller (버튼 입력)
    window.start_camera_requested.connect(controller.start_camera)
    window.measurement_requested.connect(controller.request_measurement)
    window.stop_camera_requested.connect(controller.stop_camera)
    window.close_requested.connect(controller.shutdown)

    # Controller → GUI (상태/결과 표시)
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
    parser = argparse.ArgumentParser(description="Run the threaded GUI app with metrics.")
    parser.add_argument(
        "--camera-index",
        "-c",
        type=int,
        default=0,
        help="OpenCV camera index. Try 1 or 2 for DroidCam.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs/threaded_runs",
        help="Directory where CSV/JSON run metrics are saved.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):  # 프로그램 시작 함수 (PyQt5 GUI 진입점)
    args = parse_args(argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # High DPI 스케일링
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # High DPI 픽스맵

    app = QApplication(sys.argv[:1])  # GUI Qt 이벤트 루프 생성
    app.setStyle("Fusion")  # Fusion 스타일 적용

    # 순환 import를 피하기 위해 함수 내부에서 import
    from face_age_gender_predictor.app.main_window import AgeEstimatorWindow

    controller = SystemController(
        camera_index=args.camera_index,
        log_dir=args.log_dir,
    )  # Sys Controller 생성
    window = AgeEstimatorWindow()  # GUI 창 생성

    connect_window_and_controller(window, controller)  # GUI와 Controller 연결

    app.aboutToQuit.connect(controller.shutdown)  # 앱 종료 직전 정리 함수 연결

    window.show()  # GUI 창 표시

    sys.exit(app.exec_())  # Qt 이벤트 루프 실행


if __name__ == "__main__":  # 이 파일을 직접 실행했을 때만
    main(sys.argv[1:])  # main 함수 실행
