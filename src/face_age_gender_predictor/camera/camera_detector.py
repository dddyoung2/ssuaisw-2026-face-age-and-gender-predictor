"""
camera_detector.py
==================
역할:
  1. 카메라 프레임을 계속 읽으며 얼굴을 감지합니다.
  2. 얼굴이 1명 이상 감지되면 on_single_person_detected 콜백을 호출합니다.
     얼굴이 감지되지 않으면 on_no_single_person 콜백을 호출합니다.
  3. start_recording() 호출 시 감지를 잠시 비활성화하고 40프레임을 캡처합니다.
  4. 캡처가 끝나면 on_frames_ready(frames) 콜백을 호출합니다.

사용 예시:
  detector = CameraDetector(
      on_single_person_detected=lambda: ...,
      on_no_single_person=lambda: ...,
      on_frames_ready=lambda frames: ...,
  )
  detector.start()
"""

import cv2
import time
import threading
import numpy as np
from typing import Callable, List, Optional

# OpenCV Haar cascade 얼굴 감지기
_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

TOTAL_FRAMES = 40    # 캡처할 프레임 수


class CameraDetector:
    def __init__(
        self,
        on_single_person_detected: Callable[[], None],
        on_frames_ready: Callable[[List[np.ndarray]], None],
        camera_index: int = 0,
        on_no_single_person: Optional[Callable[[], None]] = None,
    ):
        """
        on_single_person_detected : 얼굴 감지 상태로 진입했을 때 호출되는 콜백
        on_frames_ready           : 40프레임 캡처 완료 후 호출되는 콜백
        camera_index              : 카메라 번호 (기본값 0)
        on_no_single_person       : 얼굴이 감지되지 않을 때 호출되는 콜백 (선택)
        """
        self.on_single_person_detected = on_single_person_detected
        self.on_frames_ready = on_frames_ready
        self.on_no_single_person = on_no_single_person
        self.camera_index = camera_index

        self._cap: Optional[cv2.VideoCapture] = None
        self._running   = False
        self._recording = False
        self._detecting = True   # False이면 얼굴 감지 중단
        self._latest_frame = None
        self._latest_faces = []

        # 얼굴 준비 상태 안정화용 변수
        self._last_face_ready = None
        self._candidate_ready = None
        self._stable_count = 0
        self._stable_threshold = 5

    # 공개 메서드

    def start(self):
        """카메라 감지 루프 시작"""
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"카메라 {self.camera_index}를 열 수 없습니다.")
        self._running = True
        threading.Thread(target=self._detect_loop, daemon=True).start()
        print("[카메라] 감지 시작")

    def stop(self):
        """카메라 종료"""
        self._running = False
        if self._cap:
            self._cap.release()
        print("[카메라] 종료")

    def start_recording(self):
        """현재 카메라에서 40프레임 캡처 시작"""
        if not self._recording:
            self._recording = True
            self._detecting = False   # 감지 비활성화
            threading.Thread(target=self._record_frames, daemon=True).start()

    @property
    def is_recording(self) -> bool:
        return self._recording

    # 내부 메서드

    def _detect_faces(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return faces

    def _detect_loop(self):
        """카메라 프레임을 읽고 얼굴 준비 상태를 갱신합니다."""
        while self._running:
            ret, frame = self._cap.read()

            if not ret:
                time.sleep(0.03)
                continue

            faces = self._detect_faces(frame)

            self._latest_frame = frame.copy()
            self._latest_faces = faces

            count = len(faces)

            # 얼굴 준비: 얼굴이 1명 이상이면 준비 완료
            face_ready_now = count >= 1

            # 상태 안정화: 같은 상태가 일정 프레임 이상 유지되는지 확인
            if face_ready_now == self._candidate_ready:
                self._stable_count += 1
            else:
                self._candidate_ready = face_ready_now
                self._stable_count = 1

            # 안정화 기준에 도달하기 전에는 콜백 호출을 보류
            if self._stable_count < self._stable_threshold:
                time.sleep(0.03)
                continue

            # 이전 상태와 같으면 콜백 중복 호출을 방지
            if face_ready_now == self._last_face_ready:
                time.sleep(0.03)
                continue

            self._last_face_ready = face_ready_now

            if self._detecting and not self._recording:
                if face_ready_now:
                    print(f"[카메라] 얼굴 감지됨 ({count}명) → 준비 완료")

                    threading.Thread(
                        target=self.on_single_person_detected,
                        daemon=True
                    ).start()

                else:
                    print("[카메라] 얼굴 미감지 → 준비 해제")

                    if self.on_no_single_person:
                        threading.Thread(
                            target=self.on_no_single_person,
                            daemon=True
                        ).start()

            time.sleep(0.03)

    def _record_frames(self):
        """40프레임을 연속 캡처한 뒤 한 번에 콜백으로 전달합니다."""
        frames = []

        print(f"[카메라] 촬영 시작 ({TOTAL_FRAMES}프레임 캡처 중...)")
        while len(frames) < TOTAL_FRAMES:
            ret, frame = self._cap.read()
            if ret:
                frames.append(frame)

        self._recording = False
        self._detecting = True   # 촬영 완료 후 감지 재개
        print(f"[카메라] 촬영 완료 ({len(frames)}프레임) → 추론 요청")
        self.on_frames_ready(frames)
        
    def resume_detection(self):
        """사람 수 감지 재개"""
        if self._detecting:
            print("[카메라] 이미 감지 중입니다.")
            return

        self._detecting = True

        # 상태 안정화 변수 초기화
        self._last_face_ready = None
        self._candidate_ready = None
        self._stable_count = 0

        print("[카메라] 감지 재개")
