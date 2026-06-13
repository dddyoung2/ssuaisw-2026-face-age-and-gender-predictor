import numpy as np
import time

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


def test_has_recent_face_true_during_grace_period():
    detector = _make_detector()
    detector._latest_face_box = None
    detector._last_face_seen_at = time.monotonic()

    assert detector.has_recent_face() is True


def test_has_recent_face_false_after_grace_period():
    detector = _make_detector()
    detector._latest_face_box = None
    detector._face_grace_seconds = 0.1
    detector._last_face_seen_at = time.monotonic() - 1.0

    assert detector.has_recent_face() is False


def test_face_lost_threshold_is_more_tolerant_than_face_found_threshold():
    detector = _make_detector()

    assert detector._stable_threshold_for(True) < detector._stable_threshold_for(False)


def test_resume_detection_resets_stabilization_when_already_detecting():
    """재측정 회귀 테스트.

    촬영이 끝나면 _record_frames가 _detecting=True로 되돌려 놓는다. 이 상태에서
    resume_detection()이 안정화 캐시(_last_face_ready 등)를 초기화하지 않으면,
    얼굴이 그대로 있어도 face_ready 콜백이 다시 발생하지 않아 측정 버튼이
    재활성화되지 않는다. resume_detection()은 이미 감지 중이어도 캐시를 초기화해야 한다.
    """
    detector = _make_detector()

    # 직전 측정 종료 상태를 흉내냄: 감지는 재개됐지만 준비 상태 캐시가 True로 남음
    detector._detecting = True
    detector._last_face_ready = True
    detector._candidate_ready = True
    detector._stable_count = 99

    detector.resume_detection()

    assert detector._detecting is True
    assert detector._last_face_ready is None
    assert detector._candidate_ready is None
    assert detector._stable_count == 0


def test_has_current_face_ignores_grace_period():
    """has_current_face는 grace period를 적용하지 않고 현재 bbox 유무만 본다."""
    detector = _make_detector()
    detector._latest_face_box = None
    detector._last_face_seen_at = time.monotonic()

    assert detector.has_recent_face() is True     # grace로는 True
    assert detector.has_current_face() is False    # 현재 기준으로는 False


def test_start_recording_aborts_when_only_grace_period_face():
    """촬영 직전 재검증 회귀 테스트.

    얼굴이 방금 사라져 grace period(has_recent_face)만 True이고 현재 유효 bbox가
    없을 때, 촬영은 시작되지 않고 취소되어야 한다.
    """
    aborted = {}
    detector = CameraDetector(
        on_single_person_detected=lambda: None,
        on_frames_ready=lambda frames: None,
        on_capture_aborted=lambda reason: aborted.update({"reason": reason}),
    )
    detector._latest_face_box = None
    detector._last_face_seen_at = time.monotonic()

    assert detector.has_recent_face() is True   # grace로는 통과하지만
    detector.start_recording()                  # 실제 촬영은 취소되어야 한다

    assert detector.is_recording is False
    assert "reason" in aborted


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
