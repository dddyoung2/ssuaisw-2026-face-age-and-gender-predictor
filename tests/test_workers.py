"""InferenceWorker가 frames → prediction → result_processor 경로를 따라
SystemController가 받을 result dict를 만들어내는지 확인한다.

GUI/QThread 자체는 수동 QA 영역이라, 여기서는 Qt 이벤트 루프 없이 Worker의
run()을 직접 호출해 데이터 계약(result dict)만 검증한다.
"""

import numpy as np
import pytest

from face_age_gender_predictor.app.workers import InferenceWorker


def _fake_frames(n=40):
    return [np.zeros((224, 224, 3), dtype=np.uint8) for _ in range(n)]


def test_inference_worker_emits_success_result_for_40_frames():
    captured = {}
    progress = []

    worker = InferenceWorker(_fake_frames(40))
    worker.result_ready.connect(lambda result: captured.update(result))
    worker.progress_changed.connect(lambda c, t: progress.append((c, t)))

    worker.run()

    assert captured.get("success") is True
    assert captured["valid_count"] == 40
    assert captured["reason"] is None
    assert captured["gender"] in (0, 1)
    assert len(captured["age_probs"]) == 26
    # 진행률은 1..40 까지 보고된다.
    assert progress[0] == (1, 40)
    assert progress[-1] == (40, 40)


def test_inference_worker_reports_error_on_empty_frames():
    errors = []

    worker = InferenceWorker([])
    worker.error_occurred.connect(lambda msg: errors.append(msg))

    worker.run()

    assert len(errors) == 1
    assert "프레임" in errors[0]


def test_inference_worker_routes_processing_failure_to_error(monkeypatch):
    """추론/후처리 단계에서 예외가 나도(예: 모델 파일 없음) 앱 크래시 대신
    error_occurred로 전달되고 finished도 emit되는지 확인한다."""
    import face_age_gender_predictor.app.workers as workers_mod

    def boom(predictions, on_result_ready):
        raise RuntimeError("model file not found")

    monkeypatch.setattr(workers_mod, "process_predictions", boom)

    errors = []
    finished = []
    results = []

    worker = InferenceWorker(_fake_frames(40))
    worker.error_occurred.connect(lambda msg: errors.append(msg))
    worker.finished.connect(lambda: finished.append(True))
    worker.result_ready.connect(lambda r: results.append(r))

    worker.run()  # 예외가 밖으로 전파되면 테스트가 실패한다(크래시 방지 확인)

    assert results == []  # 결과는 전달되지 않는다
    assert len(errors) == 1
    assert "model file not found" in errors[0]
    assert finished == [True]  # 실패해도 종료 정리는 수행된다
