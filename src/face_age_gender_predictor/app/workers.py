# workers.py

from typing import List, Optional, Tuple  # 타입 힌트를 위해 사용

import numpy as np  # OpenCV frame 타입 표시를 위해 사용
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot  # PyQt Signal/Slot과 Worker 객체를 위해 사용

# 기존 카메라 감지기 클래스 가져오기
from face_age_gender_predictor.camera.camera_detector import CameraDetector
# 실제 TorchScript 모델 추론 API 가져오기
from face_age_gender_predictor.inference.CNNmodel import predict_frames
# 기존 결과 후처리 함수 가져오기
from face_age_gender_predictor.processing.result_processor import process_predictions


class CameraBridgeWorker(QObject):
    """CameraDetector를 PyQt Signal/Slot 구조로 감싸는 Worker (CameraThread에서 실행)"""

    started = pyqtSignal()  # 카메라 감지가 실제로 시작되었음을 알리는 signal
    status_changed = pyqtSignal(str)  # 카메라 상태 메시지를 Sys로 보내는 signal
    face_ready_changed = pyqtSignal(bool)  # 얼굴 준비 여부를 Sys로 보내는 signal
    preview_frame_ready = pyqtSignal(object)  # (frame, face_box) 미리보기 프레임 signal
    capture_progress = pyqtSignal(int, int)  # 40프레임 캡처 진행률 signal
    frames_ready = pyqtSignal(object)  # 40프레임 캡처 결과를 Sys로 보내는 signal
    error_occurred = pyqtSignal(str)  # 카메라 오류 메시지를 Sys로 보내는 signal
    finished = pyqtSignal()  # Worker 종료를 알리는 signal

    def __init__(self, camera_index: int = 0):  # 카메라 번호를 받아 초기화
        super().__init__()  # QObject 초기화
        self.camera_index = camera_index  # 사용할 카메라 번호 저장
        self.detector: Optional[CameraDetector] = None  # CameraDetector 객체 저장 공간

    @pyqtSlot()  # 이 함수가 slot으로 호출될 수 있음을 표시
    def start_camera(self):  # 카메라 감지 시작 함수
        try:  # 카메라 실행 중 오류를 잡기 위한 try
            self.status_changed.emit("[CameraWorker] 카메라 시작 요청")  # 상태 메시지 emit

            self.detector = CameraDetector(  # 기존 CameraDetector 객체 생성
                on_single_person_detected=self._on_face_detected,  # 얼굴 감지 콜백 연결
                on_no_single_person=self._on_face_not_detected,  # 얼굴 미감지 콜백 연결
                on_frames_ready=self._on_frames_ready,  # 40프레임 완료 콜백 연결
                on_preview_frame=self._on_preview_frame,  # 미리보기 프레임 콜백 연결
                on_capture_progress=self._on_capture_progress,  # 캡처 진행률 콜백 연결
                on_capture_aborted=self._on_capture_aborted,  # 캡처 직전 재검증 실패 콜백 연결
                camera_index=self.camera_index,  # 사용할 카메라 번호 전달
            )

            self.detector.start()  # CameraDetector 내부 카메라 감지 시작
            self.status_changed.emit("[CameraWorker] 카메라 감지 실행 중")  # 시작 완료 메시지 emit
            self.started.emit()  # 카메라가 실제로 시작되었음을 알림

        except Exception as e:  # 카메라 열기 실패 등 예외 처리
            self.detector = None  # 시작 실패한 detector 참조 제거
            self.error_occurred.emit(str(e))  # 오류 메시지를 Sys로 전달
            self.finished.emit()  # 실패 시 Thread/참조 정리를 위해 종료 signal emit

    @pyqtSlot()  # slot으로 호출될 수 있게 표시
    def start_capture(self):  # 40프레임 촬영 시작 함수
        if self.detector is None:  # detector가 아직 없으면
            self.error_occurred.emit("카메라가 아직 시작되지 않았습니다.")  # 오류 전달
            return  # 함수 종료

        if self.detector.is_recording:  # 이미 촬영 중이면
            self.status_changed.emit("[CameraWorker] 이미 촬영 중입니다.")  # 중복 촬영 방지 메시지
            return  # 함수 종료

        # 촬영 직전 얼굴 재검증은 CameraDetector.start_recording 내부에서도 수행한다.
        self.status_changed.emit("[CameraWorker] 40프레임 촬영 시작")  # 촬영 시작 메시지
        self.detector.start_recording()  # CameraDetector에 40프레임 촬영 요청

    @pyqtSlot()  # slot으로 호출될 수 있게 표시
    def resume_detection(self):  # 얼굴 감지 재개 함수
        if self.detector is None:  # detector가 없으면
            self.error_occurred.emit("카메라가 아직 시작되지 않았습니다.")  # 오류 전달
            return  # 함수 종료

        self.detector.resume_detection()  # CameraDetector의 감지 재개 함수 호출
        self.status_changed.emit("[CameraWorker] 감지 재개 요청 완료")  # 상태 메시지 전달

    @pyqtSlot()  # slot으로 호출될 수 있게 표시
    def stop_camera(self):  # 카메라 종료 함수
        try:  # 종료 중 오류를 잡기 위한 try
            if self.detector is not None:  # detector가 존재하면
                self.detector.stop()  # 카메라 종료
                self.detector = None  # detector 참조 제거

            self.status_changed.emit("[CameraWorker] 카메라 종료")  # 종료 메시지 emit

        except Exception as e:  # 종료 중 오류 발생 시
            self.error_occurred.emit(str(e))  # 오류 메시지 emit

        finally:  # 성공/실패와 관계없이
            self.finished.emit()  # Worker 종료 signal emit

    def _on_face_detected(self):  # CameraDetector의 얼굴 감지 콜백
        self.face_ready_changed.emit(True)  # 얼굴 준비 완료 signal emit

    def _on_face_not_detected(self):  # CameraDetector의 얼굴 미감지 콜백
        self.face_ready_changed.emit(False)  # 얼굴 준비 해제 signal emit

    def _on_preview_frame(self, frame: np.ndarray, face_box):  # 미리보기 프레임 콜백
        self.preview_frame_ready.emit((frame, face_box))  # (frame, box) 튜플을 Sys로 전달

    def _on_capture_progress(self, current: int, total: int):  # 캡처 진행률 콜백
        self.capture_progress.emit(current, total)  # 진행률 signal emit

    def _on_capture_aborted(self, reason: str):  # 촬영 직전 재검증 실패 콜백
        self.error_occurred.emit(reason)  # 실패 사유를 오류로 전달

    def _on_frames_ready(self, frames: List[np.ndarray]):  # CameraDetector의 40프레임 완료 콜백
        self.status_changed.emit(f"[CameraWorker] {len(frames)}프레임 수신 완료")  # 프레임 수 메시지
        self.frames_ready.emit(frames)  # Sys로 frames 전달


class InferenceWorker(QObject):
    """40프레임을 받아 실제 TorchScript 모델 추론 후 result_processor까지 실행하는
    Worker (InferenceThread에서 실행)

    추론은 CNNmodel.predict_frames(frames)를 통해 수행한다. 모델 로드/전처리/추론은
    모두 이 Worker가 실행되는 InferenceThread에서 일어나며 GUI MainThread를 막지 않는다.
    모델 파일 없음/로드 실패/추론 실패 같은 전역 오류는 error_occurred로 GUI에 전달되어
    앱이 크래시하지 않는다(임의의 임시 예측값으로 대체하지 않는다).
    """

    progress_changed = pyqtSignal(int, int)  # 추론 진행률 signal
    result_ready = pyqtSignal(dict)  # 최종 result dict signal
    error_occurred = pyqtSignal(str)  # 오류 메시지 signal
    finished = pyqtSignal()  # Worker 종료 signal

    def __init__(self, frames: List[np.ndarray]):  # frames를 받아 초기화
        super().__init__()  # QObject 초기화
        self.frames = frames  # 전달받은 40프레임 저장

    @pyqtSlot()  # QThread 시작 시 slot으로 실행될 함수
    def run(self):  # 추론 작업 실행 함수
        try:  # 추론 중 오류를 잡기 위한 try
            if not self.frames:  # frames가 비어 있으면
                raise ValueError("추론할 프레임이 없습니다.")  # 명시적 오류 발생

            total = len(self.frames)  # 전체 프레임 수 저장

            # 실제 모델 추론(InferenceThread에서 실행). 전처리 실패 프레임은 내부에서
            # 건너뛰고, 모델 파일 없음 등 전역 오류는 예외로 전파된다.
            predictions = predict_frames(
                self.frames,
                progress_callback=lambda current: self.progress_changed.emit(current, total),
            )

            process_predictions(  # 유효 prediction 수로 성공/실패를 판단하는 후처리
                predictions,  # 모델 prediction 리스트 전달
                on_result_ready=self._on_result_ready,  # 결과 콜백 연결
            )

        except Exception as e:  # 추론 중 오류 발생 시
            self.error_occurred.emit(str(e))  # 오류 메시지를 Sys로 전달

        finally:  # 성공/실패와 관계없이
            self.finished.emit()  # Worker 종료 signal emit

    def _on_result_ready(self, result: dict):  # result_processor가 호출할 콜백
        self.result_ready.emit(result)  # 최종 result를 Sys로 전달


class ConsoleCommandWorker(QObject):
    """콘솔 입력을 받는 보조 Worker (GUI 기본 흐름에서는 사용하지 않음, 디버그용)"""

    command_entered = pyqtSignal(str)  # 사용자가 입력한 명령어를 보내는 signal
    finished = pyqtSignal()  # 콘솔 Worker 종료 signal

    def __init__(self):  # 생성자
        super().__init__()  # QObject 초기화
        self._running = True  # 입력 루프 실행 여부 저장

    @pyqtSlot()  # QThread 시작 시 실행될 slot
    def run(self):  # 콘솔 입력 루프
        while self._running:  # 실행 중이면 반복
            try:  # 입력 중 오류를 잡기 위한 try
                command = input("\n명령 입력 [s=측정, r=감지재개, q=종료]: ").strip().lower()  # 명령 입력 받기
                self.command_entered.emit(command)  # 입력 명령을 Sys로 전달

                if command == "q":  # q를 입력하면
                    break  # 입력 루프 종료

            except EOFError:  # 입력 스트림이 닫힌 경우
                break  # 입력 루프 종료

        self.finished.emit()  # Worker 종료 signal emit

    @pyqtSlot()  # 외부에서 stop 요청을 받을 slot
    def stop(self):  # 입력 Worker 정지 함수
        self._running = False  # 반복 조건 해제
