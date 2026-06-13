# -*- coding: utf-8 -*-
"""GUI preview crop helper tests."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from face_age_gender_predictor.app.main_window import AgeEstimatorWindow


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


def _uniform_probs():
    # 26개(15~40세) 균등 확률분포
    return [1.0 / 26] * 26


def test_age_confidence_uses_plus_minus_two_window():
    """예측 나이 ±2세(5개 클래스)의 확률 질량을 사용한다."""
    probs = _uniform_probs()
    conf = AgeEstimatorWindow._compute_age_confidence(probs, 25.0)
    # 25세 중심 ±2 → 23,24,25,26,27 (5개 클래스) × (1/26) × 100
    expected = (5.0 / 26) * 100.0
    assert conf == pytest.approx(expected)
    # 단일 클래스 최댓값(기존 방식, 1/26×100)보다 큰 값이어야 한다.
    assert conf > (1.0 / 26) * 100.0


def test_age_confidence_clamped_to_0_100():
    """윈도우 확률 합이 1.0을 넘어도 표시값은 100%로 clamp된다."""
    probs = [1.0] * 26  # 비정상적으로 큰 확률 → 윈도우 합이 100% 초과
    conf = AgeEstimatorWindow._compute_age_confidence(probs, 25.0)
    assert conf == 100.0
    assert 0.0 <= conf <= 100.0


def test_age_confidence_window_clipped_at_age_range_boundary():
    """예측 나이가 경계(15세)면 범위 밖(13,14세) 클래스는 제외하고 합산한다."""
    probs = _uniform_probs()
    conf = AgeEstimatorWindow._compute_age_confidence(probs, 15.0)
    # 15세 중심 ±2 중 유효한 것은 15,16,17 (3개) → 13,14세는 범위 밖 제외
    expected = (3.0 / 26) * 100.0
    assert conf == pytest.approx(expected)
    assert 0.0 <= conf <= 100.0


def test_age_confidence_handles_empty_or_none():
    assert AgeEstimatorWindow._compute_age_confidence([], 25.0) == 0.0
    assert AgeEstimatorWindow._compute_age_confidence(_uniform_probs(), None) == 0.0
