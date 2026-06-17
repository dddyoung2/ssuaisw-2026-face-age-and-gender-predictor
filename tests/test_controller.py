from face_age_gender_predictor.app.main_app import AppState, SystemController


class _DetectorStub:
    def __init__(self):
        self.reset_count = 0

    def reset_ready_state(self):
        self.reset_count += 1


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


def test_success_returns_to_idle_and_resets_detector(qapp, tmp_path):
    controller = SystemController(log_dir=tmp_path)
    detector = _DetectorStub()
    controller.detector = detector
    controller.camera_running = True
    controller.face_ready = True
    controller.metrics.start_run(camera_index=0)
    controller.metrics.mark("measurement_requested")
    controller.metrics.mark("result_ready")

    enabled = []
    controller.measure_button_enabled_changed.connect(lambda e: enabled.append(e))

    controller.on_inference_done(_success_result())

    assert controller.state == AppState.IDLE
    assert controller.face_ready is False
    assert detector.reset_count == 1
    assert enabled[-1] is False


def test_second_measurement_after_redetect(qapp, tmp_path):
    controller = SystemController(log_dir=tmp_path)
    controller.detector = _DetectorStub()
    controller.camera_running = True
    controller.face_ready = True

    controller._return_to_idle()
    assert controller.state == AppState.IDLE

    enabled = []
    controller.measure_button_enabled_changed.connect(lambda e: enabled.append(e))

    controller.face_ready = True
    controller._emit_measure_enabled()
    assert enabled[-1] is True

    controller.request_measurement()
    assert controller.state == AppState.COUNTDOWN
    assert controller.metrics.is_active is True
    assert "measurement_requested" in controller.metrics._marks
    controller.countdown_timer.stop()


def test_failure_recovers_to_idle(qapp, tmp_path):
    controller = SystemController(log_dir=tmp_path)
    detector = _DetectorStub()
    controller.detector = detector
    controller.camera_running = True
    controller.face_ready = True

    errors = []
    controller.error_occurred.connect(lambda msg: errors.append(msg))

    controller.on_error("measurement failed")

    assert errors == ["measurement failed"]
    assert controller.state == AppState.IDLE
    assert controller.face_ready is False
    assert detector.reset_count == 1


def test_measure_request_ignored_when_busy(qapp, tmp_path):
    controller = SystemController(log_dir=tmp_path)
    controller.detector = _DetectorStub()
    controller.camera_running = True
    controller.face_ready = True

    controller.request_measurement()
    assert controller.state == AppState.COUNTDOWN

    controller.request_measurement()
    assert controller.state == AppState.COUNTDOWN
    controller.countdown_timer.stop()
