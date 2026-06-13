import numpy as np

from face_age_gender_predictor.camera.camera_detector import CameraDetector


def _make_detector():
    return CameraDetector(
        on_single_person_detected=lambda: None,
        on_frames_ready=lambda frames: None,
        on_no_single_person=lambda: None,
    )


def test_largest_face_box_returns_none_for_empty():
    assert CameraDetector._largest_face_box([]) is None
    assert CameraDetector._largest_face_box(np.empty((0, 4), dtype=int)) is None


def test_largest_face_box_picks_largest_area():
    faces = [
        (0, 0, 10, 10),    # area 100
        (5, 5, 40, 30),    # area 1200 (largest)
        (1, 1, 20, 20),    # area 400
    ]
    assert CameraDetector._largest_face_box(faces) == (5, 5, 40, 30)


def test_has_recent_face_default_false():
    detector = _make_detector()
    assert detector.has_recent_face() is False
    assert detector.latest_face_box is None


def test_has_recent_face_true_when_box_present():
    detector = _make_detector()
    detector._latest_face_box = (1, 2, 3, 4)
    assert detector.has_recent_face() is True


def test_start_recording_aborts_without_face():
    aborted = {}
    detector = CameraDetector(
        on_single_person_detected=lambda: None,
        on_frames_ready=lambda frames: None,
        on_capture_aborted=lambda reason: aborted.update({"reason": reason}),
    )
    # 얼굴이 없는 상태에서 촬영 시도 → 재검증 실패로 중단
    detector.start_recording()

    assert detector.is_recording is False
    assert "reason" in aborted
