# -*- coding: utf-8 -*-
"""SystemController 상태 전이 테스트 (재측정 복구 흐름).

실제 카메라/추론 QThread를 띄우지 않고, 컨트롤러 콜백을 직접 호출해
성공/실패 후 IDLE 복귀와 감지 재개 요청, 측정 버튼 재활성화, 2차 측정 시작을
검증한다. (QThread 실제 실행은 수동 QA 영역)
"""

from face_age_gender_predictor.app.main_app import AppState, SystemController

# qapp 픽스처는 tests/conftest.py에서 세션 단위 offscreen QApplication으로 제공된다.


def _success_result():
    return {
        "success": True,
        "age": 25.0,
        "gender": 1,
        "age_probs": [1 / 26] * 26,
        "gender_confidence": 0.9,
        "valid_count": 40,
        "reason": None,
    }


def test_success_returns_to_idle_and_requests_resume(qapp):
    controller = SystemController()
    controller.camera_running = True
    controller.face_ready = True

    resume = []
    enabled = []
    controller.resume_detection_requested.connect(lambda: resume.append(True))
    controller.measure_button_enabled_changed.connect(lambda e: enabled.append(e))

    controller.on_inference_done(_success_result())

    assert controller.state == AppState.IDLE       # 재측정 가능한 상태로 복귀
    assert resume == [True]                         # 카메라가 켜져 있으면 감지 재개 요청
    assert controller.face_ready is False           # 다음 측정을 위해 준비 상태 초기화
    assert enabled[-1] is False                     # 완료 직후 측정 버튼 비활성화


def test_second_measurement_after_redetect(qapp):
    controller = SystemController()
    controller.camera_running = True
    controller.face_ready = True

    # 1차 측정 성공 → IDLE 복귀
    controller.on_inference_done(_success_result())
    assert controller.state == AppState.IDLE

    enabled = []
    controller.measure_button_enabled_changed.connect(lambda e: enabled.append(e))

    # 카메라가 얼굴을 다시 감지 → 측정 버튼 재활성화
    controller.on_face_ready_changed(True)
    assert enabled[-1] is True

    # 2차 측정 시작 가능 (COUNTDOWN 진입)
    controller.request_measurement()
    assert controller.state == AppState.COUNTDOWN
    controller.countdown_timer.stop()


def test_failure_recovers_to_idle_and_requests_resume(qapp):
    controller = SystemController()
    controller.camera_running = True
    controller.face_ready = True

    resume = []
    errors = []
    controller.resume_detection_requested.connect(lambda: resume.append(True))
    controller.error_occurred.connect(lambda msg: errors.append(msg))

    controller.on_error("측정 실패 시뮬레이션")

    assert errors == ["측정 실패 시뮬레이션"]
    assert controller.state == AppState.IDLE        # 실패도 재시도 가능한 IDLE로 복귀
    assert resume == [True]                         # 카메라 켜져 있으면 감지 재개 요청


def test_measure_request_ignored_when_busy(qapp):
    controller = SystemController()
    controller.camera_running = True
    controller.face_ready = True

    controller.request_measurement()
    assert controller.state == AppState.COUNTDOWN

    # 측정 진행 중 추가 요청은 무시된다(중복 측정 방지)
    controller.request_measurement()
    assert controller.state == AppState.COUNTDOWN
    controller.countdown_timer.stop()
