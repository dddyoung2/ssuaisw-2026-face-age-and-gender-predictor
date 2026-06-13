"""InferenceWorker가 frames → predict_frames → result_processor 경로를 따라
SystemController가 받을 result dict를 만들어내는지 확인한다.

GUI/QThread 자체는 수동 QA 영역이라, 여기서는 Qt 이벤트 루프 없이 Worker의
run()을 직접 호출해 데이터 계약(result dict)과 오류 라우팅만 검증한다.
실제 .pt 모델 없이 동작하도록 predict_frames는 monkeypatch로 대체한다.
"""

import numpy as np

from face_age_gender_predictor.app.workers import InferenceWorker


def _fake_frames(n=40):
    return [np.zeros((224, 224, 3), dtype=np.uint8) for _ in range(n)]


def _fake_prediction():
    return {
        "age": 30.0,
        "gender": 1.0,
        "age_probs": [1 / 26] * 26,
        "gender_confidence": 0.9,
    }


def test_inference_worker_delegates_to_predict_frames(monkeypatch):
    """Worker는 CNNmodel.predict_frames에 frames를 위임하고, 그 결과를
    result_processor를 거쳐 성공 result로 emit한다."""
    import face_age_gender_predictor.app.workers as workers_mod

    captured = {}

    def fake_predict(frames, progress_callback=None):
        captured["frames"] = frames
        total = len(frames)
        # Worker가 넘긴 progress_callback(current) 계약 확인
        if progress_callback is not None:
            for i in range(1, total + 1):
                progress_callback(i)
        return [_fake_prediction() for _ in range(total)]

    monkeypatch.setattr(workers_mod, "predict_frames", fake_predict)

    frames = _fake_frames(40)
    result = {}
    progress = []

    worker = InferenceWorker(frames)
    worker.result_ready.connect(lambda r: result.update(r))
    worker.progress_changed.connect(lambda c, t: progress.append((c, t)))

    worker.run()

    assert captured["frames"] is frames  # 위임 확인
    assert result.get("success") is True
    assert result["valid_count"] == 40
    assert result["reason"] is None
    assert result["gender"] in (0, 1)
    assert len(result["age_probs"]) == 26
    # 진행률은 (1,40) .. (40,40) 까지 보고된다.
    assert progress[0] == (1, 40)
    assert progress[-1] == (40, 40)


def test_inference_worker_reports_error_on_empty_frames():
    errors = []
    finished = []

    worker = InferenceWorker([])
    worker.error_occurred.connect(lambda msg: errors.append(msg))
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert len(errors) == 1
    assert "프레임" in errors[0]
    assert finished == [True]


def test_inference_worker_routes_model_failure_to_error(monkeypatch):
    """모델 파일 없음 등 전역 추론 오류가 예외로 전파되면, 앱 크래시 대신
    error_occurred로 전달되고 finished도 emit되는지 확인한다."""
    import face_age_gender_predictor.app.workers as workers_mod

    def boom(frames, progress_callback=None):
        raise FileNotFoundError("models/Best_Age_Estimate_model_traced.pt 없음")

    monkeypatch.setattr(workers_mod, "predict_frames", boom)

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
    assert "Best_Age_Estimate_model_traced.pt" in errors[0]
    assert finished == [True]  # 실패해도 종료 정리는 수행된다


def test_inference_worker_routes_processing_failure_to_error(monkeypatch):
    """후처리(result_processor) 단계 예외도 error_occurred로 전달되는지 확인한다."""
    import face_age_gender_predictor.app.workers as workers_mod

    monkeypatch.setattr(
        workers_mod, "predict_frames",
        lambda frames, progress_callback=None: [_fake_prediction() for _ in range(40)],
    )

    def boom(predictions, on_result_ready):
        raise RuntimeError("후처리 실패")

    monkeypatch.setattr(workers_mod, "process_predictions", boom)

    errors = []
    finished = []

    worker = InferenceWorker(_fake_frames(40))
    worker.error_occurred.connect(lambda msg: errors.append(msg))
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert len(errors) == 1
    assert "후처리 실패" in errors[0]
    assert finished == [True]
