# main_app.py

import sys  # 프로그램 실행/종료 인자를 다루기 위해 사용
from enum import Enum, auto  # 상태 Enum을 만들기 위해 사용

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QCoreApplication, QTimer  # PyQt 핵심 클래스 import

from workers import CameraBridgeWorker, InferenceWorker, ConsoleCommandWorker  # Worker 클래스들 import


class AppState(Enum):
    """프로그램 내부 상태 정의"""

    IDLE = auto()  # 대기 상태
    COUNTDOWN = auto()  # 카운트다운 상태
    CAPTURING = auto()  # 40프레임 촬영 상태
    ANALYZING = auto()  # 추론/후처리 상태
    DONE = auto()  # 성공 완료 상태
    ERROR = auto()  # 오류 상태


class SystemController(QObject):
    """GUI 없이 전체 흐름을 제어하는 Sys Controller"""

    start_capture_requested = pyqtSignal()  # CameraWorker에 40프레임 촬영을 요청하는 signal
    resume_detection_requested = pyqtSignal()  # CameraWorker에 감지 재개를 요청하는 signal
    stop_camera_requested = pyqtSignal()  # CameraWorker에 카메라 종료를 요청하는 signal
    stop_console_requested = pyqtSignal()  # ConsoleWorker에 종료를 요청하는 signal

    def __init__(self):  # 생성자
        super().__init__()  # QObject 초기화

        self.state = AppState.IDLE  # 초기 상태는 IDLE
        self.face_ready = False  # 얼굴 준비 여부 초기값
        self.countdown_value = 3  # 카운트다운 시작 숫자

        self.camera_thread = None  # 카메라 QThread 저장 공간
        self.camera_worker = None  # 카메라 Worker 저장 공간

        self.inference_thread = None  # 추론 QThread 저장 공간
        self.inference_worker = None  # 추론 Worker 저장 공간

        self.console_thread = None  # 콘솔 QThread 저장 공간
        self.console_worker = None  # 콘솔 Worker 저장 공간

        self.countdown_timer = QTimer(self)  # 카운트다운용 타이머 생성
        self.countdown_timer.setInterval(1000)  # 1초마다 timeout 발생
        self.countdown_timer.timeout.connect(self._on_countdown_tick)  # timeout을 countdown 처리 함수에 연결

        self._shutting_down = False  # 종료 중복 호출 방지 플래그

    def start(self):  # 전체 시스템 시작 함수
        self._print_header()  # 사용법 출력
        self._start_camera_worker()  # 카메라 WorkerThread 시작
        self._start_console_worker()  # 콘솔 입력 WorkerThread 시작

    def _print_header(self):  # 시작 안내 출력 함수
        print("\n========== GUI 없는 1단계 QThread 통합 테스트 ==========")  # 제목 출력
        print("s : 얼굴 준비 완료 상태에서 3초 카운트다운 후 40프레임 촬영")  # s 설명
        print("r : 카메라 얼굴 감지 재개")  # r 설명
        print("q : 프로그램 종료")  # q 설명
        print("=====================================================\n")  # 구분선 출력

    def _set_state(self, new_state: AppState):  # 상태 변경 함수
        self.state = new_state  # 새 상태 저장
        print(f"[Sys] 상태 변경 → {self.state.name}")  # 상태 변경 출력

    def _start_camera_worker(self):  # 카메라 WorkerThread 시작 함수
        self.camera_thread = QThread()  # 카메라용 QThread 생성
        self.camera_worker = CameraBridgeWorker(camera_index=0)  # 카메라 Worker 생성

        self.camera_worker.moveToThread(self.camera_thread)  # Worker를 카메라 Thread로 이동

        self.camera_thread.started.connect(self.camera_worker.start_camera)  # Thread 시작 시 카메라 시작
        self.camera_worker.status_changed.connect(self.on_status_changed)  # 카메라 상태 메시지 연결
        self.camera_worker.face_ready_changed.connect(self.on_face_ready_changed)  # 얼굴 준비 signal 연결
        self.camera_worker.frames_ready.connect(self.on_frames_ready)  # 40프레임 완료 signal 연결
        self.camera_worker.error_occurred.connect(self.on_error)  # 카메라 오류 signal 연결

        self.start_capture_requested.connect(self.camera_worker.start_capture)  # Sys 촬영 요청을 CameraWorker slot에 연결
        self.resume_detection_requested.connect(self.camera_worker.resume_detection)  # Sys 감지 재개 요청 연결
        self.stop_camera_requested.connect(self.camera_worker.stop_camera)  # Sys 종료 요청 연결

        self.camera_worker.finished.connect(self.camera_thread.quit)  # Worker 종료 시 Thread 종료
        self.camera_worker.finished.connect(self.camera_worker.deleteLater)  # Worker 객체 정리
        self.camera_thread.finished.connect(self.camera_thread.deleteLater)  # Thread 객체 정리

        self.camera_thread.start()  # 카메라 Thread 시작

    def _start_console_worker(self):  # 콘솔 입력 WorkerThread 시작 함수
        self.console_thread = QThread()  # 콘솔용 QThread 생성
        self.console_worker = ConsoleCommandWorker()  # 콘솔 입력 Worker 생성

        self.console_worker.moveToThread(self.console_thread)  # Worker를 콘솔 Thread로 이동

        self.console_thread.started.connect(self.console_worker.run)  # Thread 시작 시 입력 루프 실행
        self.console_worker.command_entered.connect(self.on_command_entered)  # 입력 명령 signal 연결
        self.stop_console_requested.connect(self.console_worker.stop)  # 종료 요청 signal 연결

        self.console_worker.finished.connect(self.console_thread.quit)  # Worker 종료 시 Thread 종료
        self.console_worker.finished.connect(self.console_worker.deleteLater)  # Worker 객체 정리
        self.console_thread.finished.connect(self.console_thread.deleteLater)  # Thread 객체 정리

        self.console_thread.start()  # 콘솔 Thread 시작

    @pyqtSlot(str)  # 문자열 status를 받는 slot
    def on_status_changed(self, message: str):  # 상태 메시지 수신 함수
        print(message)  # 상태 메시지 출력

    @pyqtSlot(bool)  # bool 값을 받는 slot
    def on_face_ready_changed(self, ready: bool):  # 얼굴 준비 상태 수신 함수
        self.face_ready = ready  # 얼굴 준비 상태 저장

        if ready:  # 얼굴이 준비되었으면
            print("[Sys] 얼굴 감지됨 → 측정 준비 완료")  # 준비 완료 출력
        else:  # 얼굴이 준비되지 않았으면
            print("[Sys] 얼굴 미감지 → 측정 불가")  # 준비 해제 출력

    @pyqtSlot(str)  # 콘솔 명령 문자열을 받는 slot
    def on_command_entered(self, command: str):  # 콘솔 명령 처리 함수
        if command == "s":  # s 입력이면
            self.request_measurement()  # 측정 요청 처리
        elif command == "r":  # r 입력이면
            self.resume_detection_requested.emit()  # 감지 재개 요청 emit
        elif command == "q":  # q 입력이면
            self.shutdown()  # 프로그램 종료 처리
        else:  # 알 수 없는 명령이면
            print("[Sys] 알 수 없는 명령입니다. s, r, q 중 하나를 입력하세요.")  # 안내 출력

    def request_measurement(self):  # 측정 요청 함수
        if self.state != AppState.IDLE:  # IDLE 상태가 아니면
            print(f"[Sys] 현재 상태가 {self.state.name}이므로 측정 요청을 무시합니다.")  # 무시 메시지
            return  # 함수 종료

        if not self.face_ready:  # 얼굴 준비가 안 되었으면
            print("[Sys] 얼굴이 준비되지 않았습니다. 먼저 카메라에 얼굴을 맞춰주세요.")  # 안내 출력
            return  # 함수 종료

        self._set_state(AppState.COUNTDOWN)  # 상태를 COUNTDOWN으로 변경
        print("[Sys] 측정 버튼 비활성화라고 가정")  # GUI 없는 테스트용 출력
        self.countdown_value = 3  # 카운트다운 값을 3으로 초기화
        self.countdown_timer.start()  # 카운트다운 타이머 시작
        self._on_countdown_tick()  # 첫 숫자를 즉시 출력

    def _on_countdown_tick(self):  # 카운트다운 tick 처리 함수
        if self.state != AppState.COUNTDOWN:  # COUNTDOWN 상태가 아니면
            self.countdown_timer.stop()  # 타이머 정지
            return  # 함수 종료

        if self.countdown_value > 0:  # 아직 카운트다운 숫자가 남아 있으면
            print(f"[Sys] 카운트다운: {self.countdown_value}")  # 현재 숫자 출력
            self.countdown_value -= 1  # 숫자 1 감소
            return  # 다음 tick 대기

        self.countdown_timer.stop()  # 카운트다운 종료 후 타이머 정지
        self.on_countdown_finished()  # 카운트다운 완료 처리 함수 호출

    def on_countdown_finished(self):  # 카운트다운 완료 처리 함수
        if self.state != AppState.COUNTDOWN:  # COUNTDOWN 상태가 아니면
            print("[Sys] 잘못된 상태의 countdown_finished 신호를 무시합니다.")  # 방어 메시지
            return  # 함수 종료

        self._set_state(AppState.CAPTURING)  # 상태를 CAPTURING으로 변경
        print("[Sys] CameraWorker에 40프레임 촬영 요청")  # 촬영 요청 메시지
        self.start_capture_requested.emit()  # CameraWorker에 촬영 요청 signal emit

    @pyqtSlot(object)  # object 타입 frames를 받는 slot
    def on_frames_ready(self, frames):  # 40프레임 수신 함수
        if self.state != AppState.CAPTURING:  # CAPTURING 상태가 아니면
            print("[Sys] 현재 촬영 상태가 아니므로 frames_ready를 무시합니다.")  # 방어 메시지
            return  # 함수 종료

        print(f"[Sys] frames_ready 수신 → {len(frames)}프레임")  # 프레임 수 출력
        self._set_state(AppState.ANALYZING)  # 상태를 ANALYZING으로 변경
        self._start_inference_worker(frames)  # 추론 WorkerThread 시작

    def _start_inference_worker(self, frames):  # 추론 WorkerThread 시작 함수
        self.inference_thread = QThread()  # 추론용 QThread 생성
        self.inference_worker = InferenceWorker(frames)  # frames를 가진 추론 Worker 생성

        self.inference_worker.moveToThread(self.inference_thread)  # Worker를 추론 Thread로 이동

        self.inference_thread.started.connect(self.inference_worker.run)  # Thread 시작 시 추론 run 실행
        self.inference_worker.progress_changed.connect(self.on_inference_progress)  # 추론 진행률 연결
        self.inference_worker.result_ready.connect(self.on_inference_done)  # 추론 결과 연결
        self.inference_worker.error_occurred.connect(self.on_error)  # 추론 오류 연결

        self.inference_worker.finished.connect(self.inference_thread.quit)  # Worker 종료 시 Thread 종료
        self.inference_worker.finished.connect(self.inference_worker.deleteLater)  # Worker 객체 정리
        self.inference_thread.finished.connect(self.inference_thread.deleteLater)  # Thread 객체 정리
        self.inference_thread.finished.connect(self._clear_inference_refs)  # 추론 참조 정리

        self.inference_thread.start()  # 추론 Thread 시작

    @pyqtSlot(int, int)  # current, total을 받는 slot
    def on_inference_progress(self, current: int, total: int):  # 추론 진행률 처리 함수
        print(f"[Sys] 분석 진행률: {current}/{total}")  # 진행률 출력

    @pyqtSlot(dict)  # result dict를 받는 slot
    def on_inference_done(self, result: dict):  # 추론 완료 처리 함수
        self._set_state(AppState.DONE)  # 상태를 DONE으로 변경

        print(  # 최종 결과 출력 시작
            f"[Sys] 최종 결과 → "  # 메시지 앞부분
            f"나이: {result['age']:.1f}세, "  # 나이 출력
            f"성별: {result['gender']}, "  # 성별 출력
            f"성별 확신도: {result['gender_confidence'] * 100:.1f}%"  # 성별 확신도 출력
        )

        print("[Sys] GUI 결과 출력이라고 가정")  # GUI 없는 테스트용 출력
        print("[Sys] 측정 버튼 재활성화라고 가정")  # GUI 없는 테스트용 출력

        self.face_ready = False  # 다음 측정을 위해 준비 상태 초기화
        self._set_state(AppState.IDLE)  # 다시 IDLE 상태로 복귀
        self.resume_detection_requested.emit()  # 카메라 감지 재개 요청

    @pyqtSlot(str)  # 오류 문자열을 받는 slot
    def on_error(self, message: str):  # 오류 처리 함수
        self._set_state(AppState.ERROR)  # 상태를 ERROR로 변경
        print(f"[Sys][ERROR] {message}")  # 오류 메시지 출력
        print("[Sys] 실패 알람 표시라고 가정")  # GUI 없는 테스트용 출력
        print("[Sys] 측정 버튼 재활성화라고 가정")  # GUI 없는 테스트용 출력
        self._set_state(AppState.IDLE)  # 오류 처리 후 IDLE로 복귀

    @pyqtSlot()  # 인자가 없는 slot
    def _clear_inference_refs(self):  # 추론 Worker 참조 정리 함수
        self.inference_thread = None  # 추론 Thread 참조 제거
        self.inference_worker = None  # 추론 Worker 참조 제거

    def shutdown(self):  # 프로그램 종료 처리 함수
        if self._shutting_down:  # 이미 종료 중이면
            return  # 중복 종료 방지

        self._shutting_down = True  # 종료 중 플래그 설정
        print("[Sys] 종료 요청 수신")  # 종료 메시지 출력

        self.stop_camera_requested.emit()  # CameraWorker에 종료 요청
        self.stop_console_requested.emit()  # ConsoleWorker에 종료 요청

        if self.countdown_timer.isActive():  # 카운트다운 타이머가 켜져 있으면
            self.countdown_timer.stop()  # 타이머 정지

        QTimer.singleShot(500, QCoreApplication.instance().quit)  # 0.5초 후 앱 종료


def main():  # 프로그램 시작 함수
    app = QCoreApplication(sys.argv)  # GUI 없는 Qt 이벤트 루프 생성

    controller = SystemController()  # Sys Controller 생성
    app.aboutToQuit.connect(controller.shutdown)  # 앱 종료 직전 정리 함수 연결

    controller.start()  # 시스템 시작

    sys.exit(app.exec_())  # Qt 이벤트 루프 실행


if __name__ == "__main__":  # 이 파일을 직접 실행했을 때만
    main()  # main 함수 실행