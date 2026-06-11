import pytest

from face_age_gender_predictor.processing.result_processor import process_predictions


def _make_prediction(age, gender, confidence, age_prob_value=1 / 26):
    return {
        "age": age,
        "gender": gender,
        "age_probs": [age_prob_value] * 26,
        "gender_confidence": confidence,
    }


def test_process_predictions_aggregates_40_predictions():
    predictions = [
        _make_prediction(age=20.0, gender=1.0, confidence=0.8)
        for _ in range(40)
    ]
    captured = {}

    process_predictions(predictions, on_result_ready=lambda result: captured.update(result))

    assert captured["age"] == pytest.approx(20.0)
    assert captured["gender"] == 1
    assert captured["gender_confidence"] == pytest.approx(0.8)
    assert len(captured["age_probs"]) == 26
    assert captured["age_probs"] == pytest.approx([1 / 26] * 26)


def test_process_predictions_uses_average_gender_threshold():
    predictions = [
        _make_prediction(age=30.0, gender=0.25, confidence=0.9)
        for _ in range(20)
    ] + [
        _make_prediction(age=30.0, gender=0.75, confidence=0.9)
        for _ in range(20)
    ]
    captured = {}

    process_predictions(predictions, on_result_ready=lambda result: captured.update(result))

    assert captured["gender"] == 1


def test_process_predictions_handles_non_40_prediction_flow():
    predictions = [
        _make_prediction(age=24.0, gender=0.0, confidence=0.7),
        _make_prediction(age=28.0, gender=0.0, confidence=0.9),
    ]
    captured = {}

    process_predictions(predictions, on_result_ready=lambda result: captured.update(result))

    assert captured["age"] == pytest.approx(26.0)
    assert captured["gender"] == 0
    assert captured["gender_confidence"] == pytest.approx(0.8)
