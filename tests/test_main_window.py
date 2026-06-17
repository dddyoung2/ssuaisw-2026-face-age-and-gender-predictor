# -*- coding: utf-8 -*-
"""GUI helper tests: preview crop + 나이 확신도(weighted stddev) 공식 + 성별 라벨 contract."""

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from face_age_gender_predictor.app.main_window import (
    AgeEstimatorWindow,
    age_confidence_from_stddev,
    age_confidence_percent,
    age_distribution_stddev,
    AGE_CONF_STDDEV_BEST,
    AGE_CONF_STDDEV_WORST,
    AGE_CONF_CONFIDENCE_BEST,
    AGE_CONF_CONFIDENCE_WORST,
)


# --------------------------------------------------------------------
# 기존 preview crop helper 테스트 (이번 작업과 무관, 유지)
# --------------------------------------------------------------------

def test_expanded_square_face_box_keeps_full_face_context():
    x, y, w, h = AgeEstimatorWindow._expanded_square_face_box(
        frame_shape=(240, 320, 3),
        face_box=(100, 80, 80, 100),
        margin=0.45,
    )

    assert x < 100
    assert y < 80
    assert x + w > 180
    assert y + h > 180
    assert w == h
    assert 0 <= x < x + w <= 320
    assert 0 <= y < y + h <= 240


# --------------------------------------------------------------------
# 분포 생성 헬퍼
# --------------------------------------------------------------------

def _uniform_probs():
    # 26개(15~40세) 균등 확률분포
    return [1.0 / 26] * 26


def _delta_probs(index=10):
    probs = [0.0] * 26
    probs[index] = 1.0
    return probs


def _two_point_probs(stddev, gap):
    """index 0과 index gap 두 곳에만 질량을 두어 정확히 target stddev를 갖는 분포.

    두 점 분포의 분산 = p(1-p) * gap^2 이므로, p(1-p) = stddev^2 / gap^2 로 두면
    표준편차가 정확히 stddev가 된다. (gap^2 >= 4*stddev^2 이어야 실수해 존재)
    """
    k = (stddev ** 2) / (gap ** 2)
    disc = 1 - 4 * k
    assert disc >= 0, "gap이 너무 작아 target stddev를 만들 수 없음"
    p = (1 - math.sqrt(disc)) / 2  # 먼 점(index gap)에 두는 질량
    probs = [0.0] * 26
    probs[0] = 1 - p
    probs[gap] = p
    return probs


# --------------------------------------------------------------------
# stddev -> confidence 매핑 (endpoint / clamp)
# --------------------------------------------------------------------

def test_mapping_best_stddev_is_99():
    assert age_confidence_from_stddev(AGE_CONF_STDDEV_BEST) == pytest.approx(99.0)


def test_mapping_worst_stddev_is_1():
    assert age_confidence_from_stddev(AGE_CONF_STDDEV_WORST) == pytest.approx(1.0)


def test_mapping_midpoint_is_50():
    mid = (AGE_CONF_STDDEV_BEST + AGE_CONF_STDDEV_WORST) / 2
    assert age_confidence_from_stddev(mid) == pytest.approx(50.0)


def test_mapping_below_best_clamps_to_99():
    assert age_confidence_from_stddev(0.0) == 99.0
    assert age_confidence_from_stddev(AGE_CONF_STDDEV_BEST - 1.0) == 99.0


def test_mapping_above_worst_clamps_to_1():
    assert age_confidence_from_stddev(20.0) == 1.0
    assert age_confidence_from_stddev(AGE_CONF_STDDEV_WORST + 5.0) == 1.0


# --------------------------------------------------------------------
# 분포 -> weighted stddev
# --------------------------------------------------------------------

def test_delta_distribution_has_zero_stddev():
    assert age_distribution_stddev(_delta_probs()) == pytest.approx(0.0)


def test_uniform_distribution_stddev_is_7_5():
    # 26개 연속 정수에 대한 균등분포의 stddev = sqrt((26^2 - 1)/12) = 7.5
    assert age_distribution_stddev(_uniform_probs()) == pytest.approx(7.5)


def test_unnormalized_positive_weights_are_normalized():
    # 균등한 unnormalized weight는 normalize 후 균등분포와 동일한 stddev
    assert age_distribution_stddev([2.0] * 26) == pytest.approx(7.5)


def test_two_point_distribution_stddev_matches_target():
    assert age_distribution_stddev(_two_point_probs(1.57, gap=8)) == pytest.approx(1.57, abs=1e-6)
    assert age_distribution_stddev(_two_point_probs(8.23, gap=17)) == pytest.approx(8.23, abs=1e-6)


# --------------------------------------------------------------------
# 분포 -> confidence (full path, calibration endpoints)
# --------------------------------------------------------------------

def test_distribution_with_best_stddev_maps_to_99():
    probs = _two_point_probs(AGE_CONF_STDDEV_BEST, gap=8)
    assert age_confidence_percent(probs) == pytest.approx(99.0, abs=1e-4)


def test_distribution_with_worst_stddev_maps_to_1():
    probs = _two_point_probs(AGE_CONF_STDDEV_WORST, gap=17)
    assert age_confidence_percent(probs) == pytest.approx(1.0, abs=1e-4)


def test_narrow_distribution_clamps_to_99():
    # stddev 0 (delta) -> 99로 clamp
    assert age_confidence_percent(_delta_probs()) == 99.0


def test_uniform_distribution_gives_low_confidence():
    conf = age_confidence_percent(_uniform_probs())
    # stddev 7.5 -> 약 11.7% (낮은 confidence)
    assert conf is not None
    assert conf < 20.0


# --------------------------------------------------------------------
# invalid input은 높은 confidence로 fallback하지 않는다
# --------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        [0.1] * 25,            # 길이 != 26
        [0.1] * 27,            # 길이 != 26
        [0.0] * 26,            # 합 0
        [-1.0] + [0.1] * 25,   # 음수 포함
        ["x"] * 26,            # 숫자가 아닌 값
        [float("nan")] * 26,   # NaN
        [float("inf")] + [0.0] * 25,  # Inf
        "not-a-list",
    ],
)
def test_invalid_distribution_returns_none(bad):
    assert age_distribution_stddev(bad) is None
    assert age_confidence_percent(bad) is None


def test_invalid_distribution_never_high_confidence():
    # 핵심 방어 조건: invalid 입력이 99% 같은 높은 confidence를 만들면 안 된다.
    for bad in (None, [], [0.0] * 26, [float("nan")] * 26):
        assert age_confidence_percent(bad) is None


# --------------------------------------------------------------------
# GUI 표시 경로가 새 공식 helper를 사용하는지
# --------------------------------------------------------------------

def test_window_compute_age_confidence_delegates_to_helper():
    probs = _two_point_probs(1.57, gap=8)
    assert AgeEstimatorWindow._compute_age_confidence(probs) == pytest.approx(
        age_confidence_percent(probs)
    )
    # 이전 ±2세 시그니처(age 인자)는 더 이상 필요 없다: 단일 인자로 호출된다.
    assert AgeEstimatorWindow._compute_age_confidence(None) is None


def test_success_display_uses_new_confidence_and_gender_label(qapp):
    window = AgeEstimatorWindow()
    try:
        probs = _two_point_probs(AGE_CONF_STDDEV_BEST, gap=8)
        result = {
            "success": True,
            "age": 25.0,
            "gender": 1,
            "age_probs": probs,
            "gender_confidence": 0.9,
            "valid_count": 35,
            "reason": None,
        }
        window._show_success_result(result)

        assert window.preview_age_confidence_value.text() == "99.0%"
        assert window.preview_gender_value.text() == "여성"
    finally:
        window.close()


def test_success_display_invalid_age_probs_shows_dash(qapp):
    window = AgeEstimatorWindow()
    try:
        result = {
            "success": True,
            "age": 25.0,
            "gender": 0,
            "age_probs": [0.0] * 26,  # invalid (합 0)
            "gender_confidence": 0.9,
            "valid_count": 35,
            "reason": None,
        }
        window._show_success_result(result)

        # invalid 분포 → 높은 confidence가 아니라 "-"
        assert window.preview_age_confidence_value.text() == "-"
        assert window.preview_gender_value.text() == "남성"
    finally:
        window.close()


@pytest.mark.parametrize(
    "bad_probs",
    [
        [float("nan")] * 26,            # NaN 포함
        [float("inf")] + [0.0] * 25,    # Inf 포함
        [0.04] * 25 + ["x"],            # 숫자가 아닌 값 포함
        [-1.0] + [0.1] * 25,            # 음수 포함
        [0.04] * 25,                    # 길이 != 26
        [0.0] * 26,                     # 합 0
    ],
)
def test_success_display_invalid_age_probs_no_exception_and_empty_histogram(qapp, bad_probs):
    """invalid age_probs는 confidence "-"와 빈 히스토그램으로 안전하게 처리되어야 한다.

    회귀 방지: 이전에는 confidence는 "-"였지만 같은 age_probs를 히스토그램 변환
    (int(round(p*1000)))에 그대로 써서 NaN 등에서 ValueError가 발생했다.
    """
    window = AgeEstimatorWindow()
    try:
        result = {
            "success": True,
            "age": 25.0,
            "gender": 1,
            "age_probs": bad_probs,
            "gender_confidence": 0.9,
            "valid_count": 35,
            "reason": None,
        }
        # 예외가 발생하면 테스트가 실패한다(크래시 방지 확인)
        window._show_success_result(result)

        assert window.preview_age_confidence_value.text() == "-"
        assert window.age_histogram.values == [0] * 26  # 빈 히스토그램
    finally:
        window.close()


# --------------------------------------------------------------------
# 성별 라벨 contract: gender == 1 -> 여성, gender == 0 -> 남성
# --------------------------------------------------------------------

def test_gender_label_contract():
    assert AgeEstimatorWindow._gender_label(1) == "여성"
    assert AgeEstimatorWindow._gender_label(0) == "남성"
