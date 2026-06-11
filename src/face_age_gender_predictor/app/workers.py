# workers.py

import time  # 짧은 대기 시간을 주기 위해 사용
import random  # 가짜 모델 예측값을 만들기 위해 사용
from typing import List, Optional  # 타입 힌트를 위해 사용

import numpy as np  # OpenCV frame 타입 표시를 위해 사용
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot  # PyQt Signal/Slot과 Worker 객체를 위해 사용

# 기존 카메라 감지기 클래스 가져오기
from face_age_gender_predictor.camera.camera_detector import CameraDetector 
# 기존 결과 후처리 함수 가져오기
from face_age_gender_predictor.processing.result_processor import process_predictions



class CameraBridgeWorker(QObject):
    """CameraDetector를 PyQt Signal/Slot 구조로 감싸는 Worker"""

    status_changed = pyqtSignal(str)  # 카메라 상태 메시지를 Sys로 보내는 signal
    face_ready_changed = pyqtSignal(bool)  # 얼굴 준비 여부를 Sys로 보내는 signal
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
                camera_index=self.camera_index,  # 사용할 카메라 번호 전달
            )

            self.detector.start()  # CameraDetector 내부 카메라 감지 시작
            self.status_changed.emit("[CameraWorker] 카메라 감지 실행 중")  # 시작 완료 메시지 emit

        except Exception as e:  # 카메라 열기 실패 등 예외 처리
            self.error_occurred.emit(str(e))  # 오류 메시지를 Sys로 전달

    @pyqtSlot()  # slot으로 호출될 수 있게 표시
    def start_capture(self):  # 40프레임 촬영 시작 함수
        if self.detector is None:  # detector가 아직 없으면
            self.error_occurred.emit("카메라가 아직 시작되지 않았습니다.")  # 오류 전달
            return  # 함수 종료

        if self.detector.is_recording:  # 이미 촬영 중이면
            self.status_changed.emit("[CameraWorker] 이미 촬영 중입니다.")  # 중복 촬영 방지 메시지
            return  # 함수 종료

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

    def _on_frames_ready(self, frames: List[np.ndarray]):  # CameraDetector의 40프레임 완료 콜백
        self.status_changed.emit(f"[CameraWorker] {len(frames)}프레임 수신 완료")  # 프레임 수 메시지
        self.frames_ready.emit(frames)  # Sys로 frames 전달


class InferenceWorker(QObject):
    """40프레임을 받아 가짜 추론 후 result_processor까지 실행하는 Worker"""

    progress_changed = pyqtSignal(int, int)  # 추론 진행률 signal
    result_ready = pyqtSignal(dict)  # 최종 결과 dict signal
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

            predictions = []  # 모델 예측 결과를 담을 리스트 생성
            total = len(self.frames)  # 전체 프레임 수 저장

            for index, frame in enumerate(self.frames, start=1):  # 각 frame을 하나씩 처리
                _ = frame  # 현재는 frame을 실제 모델에 넣지 않고 사용 표시만 함

                prediction = {  # result_processor가 요구하는 dict 형식의 가짜 예측값 생성
                    "age": random.uniform(20, 40),  # 가짜 나이 예측값
                    "gender": random.uniform(0, 1),  # 가짜 성별 원시값
                    "age_probs": [1 / 26] * 26,  # 가짜 나이 확률분포
                    "gender_confidence": random.uniform(0.7, 1.0),  # 가짜 성별 확신도
                }

                predictions.append(prediction)  # prediction 리스트에 추가
                self.progress_changed.emit(index, total)  # 진행률 signal emit
                time.sleep(0.01)  # 너무 빠르게 끝나지 않도록 짧은 대기

            process_predictions(  # 기존 result_processor 호출
                predictions,  # 가짜 prediction 40개 전달
                on_result_ready=self._on_result_ready,  # 결과 콜백 연결
            )

        except Exception as e:  # 추론 중 오류 발생 시
            self.error_occurred.emit(str(e))  # 오류 메시지를 Sys로 전달

        finally:  # 성공/실패와 관계없이
            self.finished.emit()  # Worker 종료 signal emit

    def _on_result_ready(self, result: dict):  # result_processor가 호출할 콜백
        self.result_ready.emit(result)  # 최종 result를 Sys로 전달


class ConsoleCommandWorker(QObject):
    """콘솔 입력을 받는 Worker"""

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