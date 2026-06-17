import pytest

from face_age_gender_predictor.processing.result_processor import (
    MIN_VALID_PREDICTIONS,
    process_predictions,
)


def _make_prediction(age, gender, confidence, age_prob_value=1 / 26):
    return {
        "age": age,
        "gender": gender,
        "age_probs": [age_prob_value] * 26,
        "gender_confidence": confidence,
    }


def _run(predictions):
    captured = {}
    process_predictions(predictions, on_result_ready=lambda result: captured.update(result))
    return captured


def test_success_aggregates_40_predictions():
    predictions = [
        _make_prediction(age=20.0, gender=1.0, confidence=0.8)
        for _ in range(40)
    ]
    result = _run(predictions)

    assert result["success"] is True
    assert result["valid_count"] == 40
    assert result["reason"] is None
    assert result["age"] == pytest.approx(20.0)
    assert result["gender"] == 1
    assert result["gender_confidence"] == pytest.approx(0.8)
    assert len(result["age_probs"]) == 26
    assert result["age_probs"] == pytest.approx([1 / 26] * 26)


def test_success_uses_average_gender_threshold():
    predictions = [
        _make_prediction(age=30.0, gender=0.25, confidence=0.9)
        for _ in range(20)
    ] + [
        _make_prediction(age=30.0, gender=0.75, confidence=0.9)
        for _ in range(20)
    ]
    result = _run(predictions)

    assert result["success"] is True
    assert result["gender"] == 1


def test_exactly_30_valid_is_success():
    predictions = [
        _make_prediction(age=25.0, gender=0.6, confidence=0.9)
        for _ in range(MIN_VALID_PREDICTIONS)
    ]
    result = _run(predictions)

    assert result["success"] is True
    assert result["valid_count"] == MIN_VALID_PREDICTIONS


def test_below_30_valid_is_failure_with_reason():
    predictions = [
        _make_prediction(age=24.0, gender=0.0, confidence=0.7)
        for _ in range(MIN_VALID_PREDICTIONS - 1)
    ]
    result = _run(predictions)

    assert result["success"] is False
    assert result["valid_count"] == MIN_VALID_PREDICTIONS - 1
    assert result["reason"] == "valid_count_below_30"
    assert result["age"] is None
    assert result["gender"] is None
    assert result["age_probs"] is None
    assert result["gender_confidence"] is None


def test_empty_predictions_is_failure():
    result = _run([])

    assert result["success"] is False
    assert result["valid_count"] == 0
    assert result["reason"] == "no_predictions"


def test_invalid_predictions_are_filtered_before_counting():
    # 35개는 정상, 10개는 age 가 None 이라 유효 예측에서 제외된다 → 35 >= 30 이므로 성공
    valid = [_make_prediction(age=22.0, gender=1.0, confidence=0.85) for _ in range(35)]
    invalid = [_make_prediction(age=None, gender=1.0, confidence=0.85) for _ in range(10)]
    result = _run(valid + invalid)

    assert result["success"] is True
    assert result["valid_count"] == 35
    assert result["age"] == pytest.approx(22.0)


def test_invalid_majority_drops_below_threshold():
    # 유효 29개 + 무효 20개 → 유효 29 < 30 이므로 실패
    valid = [_make_prediction(age=22.0, gender=1.0, confidence=0.85) for _ in range(29)]
    invalid = [{"age": 20.0, "gender": 1.0, "gender_confidence": 0.8, "age_probs": []} for _ in range(20)]
    result = _run(valid + invalid)

    assert result["success"] is False
    assert result["valid_count"] == 29
    assert result["reason"] == "valid_count_below_30"


# --------------------------------------------------------------------
# 성별 최종 집계 기준: average_gender >= 0.5 -> 1(여성), < 0.5 -> 0(남성)
# --------------------------------------------------------------------

def test_average_gender_above_half_is_female():
    # 평균 gender = 0.8 (>= 0.5) -> 최종 gender == 1
    predictions = [_make_prediction(age=25.0, gender=0.8, confidence=0.9) for _ in range(40)]
    result = _run(predictions)

    assert result["gender"] == 1


def test_average_gender_below_half_is_male():
    # 평균 gender = 0.2 (< 0.5) -> 최종 gender == 0
    predictions = [_make_prediction(age=25.0, gender=0.2, confidence=0.9) for _ in range(40)]
    result = _run(predictions)

    assert result["gender"] == 0


def test_average_gender_exactly_half_is_female():
    # 경계값: 평균 gender == 0.5 -> 최종 gender == 1 (여성)
    predictions = [_make_prediction(age=25.0, gender=0.5, confidence=0.9) for _ in range(40)]
    result = _run(predictions)

    assert result["gender"] == 1


def test_age_and_gender_confidence_averages_preserved_with_gender_change():
    # 성별 집계와 무관하게 age 평균/gender_confidence 평균 집계가 유지되는지 확인
    predictions = [_make_prediction(age=20.0, gender=0.1, confidence=0.6) for _ in range(20)] + [
        _make_prediction(age=30.0, gender=0.9, confidence=0.8) for _ in range(20)
    ]
    result = _run(predictions)

    assert result["age"] == pytest.approx(25.0)            # 기존 age 평균 방식 유지
    assert result["gender_confidence"] == pytest.approx(0.7)  # 기존 gender_confidence 평균 유지
    assert result["gender"] == 1                            # 평균 gender 0.5 -> 1


def test_below_threshold_fails_regardless_of_gender_average():
    # 유효 prediction 29개이고 평균 gender가 1.0이어도 실패 result가 유지된다
    predictions = [_make_prediction(age=25.0, gender=1.0, confidence=0.9) for _ in range(29)]
    result = _run(predictions)

    assert result["success"] is False
    assert result["gender"] is None
    assert result["reason"] == "valid_count_below_30"
