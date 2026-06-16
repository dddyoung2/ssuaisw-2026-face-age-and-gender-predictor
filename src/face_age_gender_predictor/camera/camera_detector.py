"""Synchronous camera detector for the single-threaded experiment branch."""

import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

TOTAL_FRAMES = 40
FaceBox = Tuple[int, int, int, int]

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


@dataclass
class CameraPollState:
    frame: Optional[np.ndarray] = None
    face_box: Optional[FaceBox] = None
    face_ready_changed: Optional[bool] = None
    capture_progress: Optional[tuple[int, int]] = None
    frames_ready: Optional[list[np.ndarray]] = None


class CameraDetector:
    """OpenCV camera helper with no internal background execution."""

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index

        self._cap: Optional[cv2.VideoCapture] = None
        self._recording = False
        self._recorded_frames: list[np.ndarray] = []
        self._latest_frame = None
        self._latest_faces = []
        self._latest_face_box: Optional[FaceBox] = None
        self._last_face_seen_at = 0.0

        self._last_face_ready = None
        self._candidate_ready = None
        self._stable_count = 0
        self._ready_on_threshold = 3
        self._ready_off_threshold = 10
        self._face_grace_seconds = 1.2

    def start(self):
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self._cap = None
            raise RuntimeError(f"카메라 {self.camera_index}를 열 수 없습니다.")
        print("[카메라] 동기식 감지 시작")

    def stop(self):
        self._recording = False
        self._recorded_frames = []
        if self._cap:
            self._cap.release()
            self._cap = None
        self._latest_frame = None
        self._latest_faces = []
        self._latest_face_box = None
        self._last_face_seen_at = 0.0
        self.reset_ready_state()
        print("[카메라] 종료")

    def start_recording(self):
        if self._recording:
            return

        if not self.has_current_face():
            raise RuntimeError("얼굴이 사라져 촬영을 시작할 수 없습니다.")

        self._recording = True
        self._recorded_frames = []

    @property
    def is_recording(self) -> bool:
        return self._recording

    def has_current_face(self) -> bool:
        return self._latest_face_box is not None

    def has_recent_face(self) -> bool:
        if self._latest_face_box is not None:
            return True
        if self._last_face_seen_at <= 0:
            return False
        return (time.monotonic() - self._last_face_seen_at) <= self._face_grace_seconds

    @property
    def latest_face_box(self) -> Optional[FaceBox]:
        return self._latest_face_box

    def reset_ready_state(self):
        self._last_face_ready = None
        self._candidate_ready = None
        self._stable_count = 0

    def poll_once(self) -> CameraPollState:
        if self._cap is None:
            raise RuntimeError("카메라가 아직 시작되지 않았습니다.")

        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("카메라 프레임을 읽지 못했습니다.")

        faces = self._detect_faces(frame)
        face_box = self._largest_face_box(faces)

        self._latest_frame = frame.copy()
        self._latest_faces = faces
        self._latest_face_box = face_box
        if face_box is not None:
            self._last_face_seen_at = time.monotonic()

        state = CameraPollState(frame=frame.copy(), face_box=face_box)

        if self._recording:
            self._recorded_frames.append(frame.copy())
            current = len(self._recorded_frames)
            state.capture_progress = (current, TOTAL_FRAMES)

            if current >= TOTAL_FRAMES:
                state.frames_ready = list(self._recorded_frames)
                self._recorded_frames = []
                self._recording = False
            return state

        face_ready_now = len(faces) >= 1 or self.has_recent_face()
        state.face_ready_changed = self._compute_ready_change(face_ready_now)
        return state

    def _detect_faces(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=4, minSize=(50, 50)
        )
        return faces

    def _stable_threshold_for(self, face_ready_now: bool) -> int:
        return self._ready_on_threshold if face_ready_now else self._ready_off_threshold

    @staticmethod
    def _largest_face_box(faces) -> Optional[FaceBox]:
        if faces is None or len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
        return int(x), int(y), int(w), int(h)

    def _compute_ready_change(self, face_ready_now: bool) -> Optional[bool]:
        if face_ready_now == self._candidate_ready:
            self._stable_count += 1
        else:
            self._candidate_ready = face_ready_now
            self._stable_count = 1

        if self._stable_count < self._stable_threshold_for(face_ready_now):
            return None

        if face_ready_now == self._last_face_ready:
            return None

        self._last_face_ready = face_ready_now
        return face_ready_now

    def resume_detection(self):
        self.reset_ready_state()
        print("[카메라] 감지 상태 초기화 (재측정 준비)")
