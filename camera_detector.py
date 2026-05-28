"""
camera_detector.py
==================
?��?��:
  1. 카메?��?��?�� ?��?��?��?�� ?��?�� ?���?(?��?��) ?���? 감�??
  2. ?��?��?�� 1�? 감�?? ?�� ?�� on_single_person_detected 콜백 ?���?
     1명이 ?��?�� ?��    ?�� on_no_single_person 콜백 ?���?
  3. start_recording() ?���? ?�� ?�� ?��?�� ?�� 감�?? 비활?��?�� ?�� 40?��?��?�� 캡처
  4. 캡처 ?���? ?��       ?�� on_frames_ready(frames) 콜백 ?���?

?��?�� ?��?��:
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

# OpenCV ?��?�� ?���? 감�??�?
_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

TOTAL_FRAMES = 40    # 캡처?�� ?��?��?�� ?��


class CameraDetector:
    def __init__(
        self,
        on_single_person_detected: Callable[[], None],
        on_frames_ready: Callable[[List[np.ndarray]], None],
        camera_index: int = 0,
        on_no_single_person: Optional[Callable[[], None]] = None,
    ):
        """
        on_single_person_detected : 1�? 감�??(진입) ?�� ?��출되?�� 콜백
        on_frames_ready           : 40?��?��?�� 캡처 ?���? ?�� ?��출되?�� 콜백
        camera_index              : 카메?�� 번호 (기본�? 0)
        on_no_single_person       : 1�? ?�� ?��?�� ?�� ?��출되?�� 콜백 (?��?��)
        """
        self.on_single_person_detected = on_single_person_detected
        self.on_frames_ready = on_frames_ready
        self.on_no_single_person = on_no_single_person
        self.camera_index = camera_index

        self._cap: Optional[cv2.VideoCapture] = None
        self._running   = False
        self._recording = False
        self._detecting = True   # False ?���? ?��?�� ?�� 감�?? 중단
        self._latest_frame = None
        self._latest_faces = []

        # �� �غ� ���� ����ȭ��
        self._last_face_ready = None
        self._candidate_ready = None
        self._stable_count = 0
        self._stable_threshold = 5

    # ?????? 공개 메서?�� ????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????

    def start(self):
        """카메?�� 감�?? 루프 ?��?��"""
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"카메?�� {self.camera_index}�? ?�� ?�� ?��?��?��?��.")
        self._running = True
        threading.Thread(target=self._detect_loop, daemon=True).start()
        print("[카메?��] 감�?? ?��?��")

    def stop(self):
        """카메?�� 종료"""
        self._running = False
        if self._cap:
            self._cap.release()
        print("[카메?��] 종료")

    def start_recording(self):
        """?���??��?�� ?���? ?�� ?��?�� ?��?��"""
        if not self._recording:
            self._recording = True
            self._detecting = False   # 감�?? 비활?��?��
            threading.Thread(target=self._record_frames, daemon=True).start()

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ?????? ?���? 메서?�� ????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????

    def _detect_faces(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return faces

    def _detect_loop(self):
        """���/�� ���� ����"""
        while self._running:
            ret, frame = self._cap.read()

            if not ret:
                time.sleep(0.03)
                continue

            faces = self._detect_faces(frame)

            self._latest_frame = frame.copy()
            self._latest_faces = faces

            count = len(faces)

            # ���� ����: ���� 1�� �̻��̸� �غ� �Ϸ�
            face_ready_now = count >= 1

            # ���� ����ȭ: ���� ���°� �������� �� ������ �����Ǵ��� Ȯ��
            if face_ready_now == self._candidate_ready:
                self._stable_count += 1
            else:
                self._candidate_ready = face_ready_now
                self._stable_count = 1

            # ���� ����� ���������� ������ �ݹ� ������ ����
            if self._stable_count < self._stable_threshold:
                time.sleep(0.03)
                continue

            # �̹� ���� ���¿� ������ �ٽ� ������ ����
            if face_ready_now == self._last_face_ready:
                time.sleep(0.03)
                continue

            self._last_face_ready = face_ready_now

            if self._detecting and not self._recording:
                if face_ready_now:
                    print(f"[ī�޶�] �� ������ ({count}��) �� �غ� �Ϸ�")

                    threading.Thread(
                        target=self.on_single_person_detected,
                        daemon=True
                    ).start()

                else:
                    print("[ī�޶�] �� �̰��� �� �غ� ����")

                    if self.on_no_single_person:
                        threading.Thread(
                            target=self.on_no_single_person,
                            daemon=True
                        ).start()

            time.sleep(0.03)

    def _record_frames(self):
        """40?��?��?��?�� 최�?? ?��?���? ?��?�� 캡처?�� ?�� ?��꺼번?�� 콜백 ?���?"""
        frames = []

        print(f"[카메?��] 촬영 ?��?�� ({TOTAL_FRAMES}?��?��?�� ?��?�� 캡처 �?...)")
        while len(frames) < TOTAL_FRAMES:
            ret, frame = self._cap.read()
            if ret:
                frames.append(frame)

        self._recording = False
        self._detecting = True   # 촬영 ?���? ?�� 감�?? ?��?��?��?��
        print(f"[카메?��] 촬영 ?���? ({len(frames)}?��?��?��) ?�� 추론 ?��?��")
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