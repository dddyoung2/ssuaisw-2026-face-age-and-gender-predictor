import time

import numpy as np

from face_age_gender_predictor.camera.camera_detector import CameraDetector


def test_largest_face_box_returns_none_for_empty():
    assert CameraDetector._largest_face_box([]) is None
    assert CameraDetector._largest_face_box(np.empty((0, 4), dtype=int)) is None


def test_largest_face_box_picks_largest_area():
    faces = [
        (0, 0, 10, 10),
        (5, 5, 40, 30),
        (1, 1, 20, 20),
    ]
    assert CameraDetector._largest_face_box(faces) == (5, 5, 40, 30)


def test_has_recent_face_default_false():
    detector = CameraDetector()
    assert detector.has_recent_face() is False
    assert detector.latest_face_box is None


def test_has_recent_face_true_when_box_present():
    detector = CameraDetector()
    detector._latest_face_box = (1, 2, 3, 4)
    assert detector.has_recent_face() is True


def test_has_recent_face_true_during_grace_period():
    detector = CameraDetector()
    detector._latest_face_box = None
    detector._last_face_seen_at = time.monotonic()

    assert detector.has_recent_face() is True


def test_has_recent_face_false_after_grace_period():
    detector = CameraDetector()
    detector._latest_face_box = None
    detector._face_grace_seconds = 0.1
    detector._last_face_seen_at = time.monotonic() - 1.0

    assert detector.has_recent_face() is False


def test_face_lost_threshold_is_more_tolerant_than_face_found_threshold():
    detector = CameraDetector()

    assert detector._stable_threshold_for(True) < detector._stable_threshold_for(False)


def test_resume_detection_resets_stabilization():
    detector = CameraDetector()
    detector._last_face_ready = True
    detector._candidate_ready = True
    detector._stable_count = 99

    detector.resume_detection()

    assert detector._last_face_ready is None
    assert detector._candidate_ready is None
    assert detector._stable_count == 0


def test_has_current_face_ignores_grace_period():
    detector = CameraDetector()
    detector._latest_face_box = None
    detector._last_face_seen_at = time.monotonic()

    assert detector.has_recent_face() is True
    assert detector.has_current_face() is False


def test_start_recording_aborts_without_current_face():
    detector = CameraDetector()
    detector._latest_face_box = None
    detector._last_face_seen_at = time.monotonic()

    try:
        detector.start_recording()
    except RuntimeError as exc:
        assert "얼굴" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")

    assert detector.is_recording is False


def test_compute_ready_change_requires_stability():
    detector = CameraDetector()
    detector._ready_on_threshold = 2
    detector._ready_off_threshold = 2

    assert detector._compute_ready_change(True) is None
    assert detector._compute_ready_change(True) is True
    assert detector._compute_ready_change(True) is None
    assert detector._compute_ready_change(False) is None
    assert detector._compute_ready_change(False) is False
