# -*- coding: utf-8 -*-
"""CNNmodel.py 추론 모듈 테스트.

실제 .pt 모델 파일 없이도 동작하도록, 모델 로드/전처리는 fake로 대체한다.
import 부작용 없음, 기본 모델 경로 해석, predict_frames 데이터 계약,
전처리 실패 프레임 skip, 모델 파일 없음 오류 메시지를 검증한다.
"""

from pathlib import Path

import numpy as np
import pytest

import face_age_gender_predictor.inference.CNNmodel as cnn


@pytest.fixture(autouse=True)
def _clear_model_cache():
    """각 테스트 전후로 모델 캐시를 초기화한다."""
    cnn.reset_model_cache()
    yield
    cnn.reset_model_cache()


# 실제 TorchScript 모델 출력 형태를 흉내내는 fake 출력
# (predicted_age, predicted_gender, age_probs(1,26), gender_confidence)
_FAKE_MODEL_OUTPUT = (27.5, 1, np.full((1, 26), 1.0 / 26, dtype=float), 0.88)


def _fake_run_model(model, device, face_rgb):
    """torch 없이 모델 추론 결과를 흉내내는 _run_model 대체.

    실제 torch 텐서 변환/forward는 _run_model 안에만 있으므로, 이 함수를 대체하면
    predict_frames의 집계/skip/progress 로직을 torch 의존성 없이 검증할 수 있다.
    """
    return _FAKE_MODEL_OUTPUT


def test_import_has_no_model_load_side_effects():
    """모듈 import만으로는 모델이 로드되지 않는다."""
    assert cnn._cached_model is None
    assert callable(cnn.predict_frames)


def test_default_model_path_is_repo_root_relative():
    """기본 모델 경로는 repo 루트의 models/Best_Age_Estimate_model_traced.pt 다."""
    repo_root = Path(__file__).resolve().parents[1]
    expected = repo_root / "models" / "Best_Age_Estimate_model_traced.pt"
    assert cnn.get_default_model_path() == expected


def test_load_model_missing_file_names_expected_path(tmp_path):
    """모델 파일이 없으면 기대 경로를 명시한 FileNotFoundError가 발생한다."""
    missing = tmp_path / "does_not_exist.pt"
    with pytest.raises(FileNotFoundError) as exc:
        cnn.load_model(missing)
    assert "models/Best_Age_Estimate_model_traced.pt" in str(exc.value)


def test_predict_frames_delegates_and_builds_contract(monkeypatch):
    """predict_frames가 모델을 호출하고 result_processor 호환 dict를 만든다."""
    monkeypatch.setattr(cnn, "_get_cached_model", lambda model_path=None: (object(), "cpu"))
    monkeypatch.setattr(cnn, "_run_model", _fake_run_model)
    # mediapipe/카메라 없이 동작하도록 전처리는 더미 RGB 이미지를 돌려준다.
    monkeypatch.setattr(
        cnn, "detect_and_align",
        lambda frame, target_size=cnn.MODEL_INPUT_SIZE: np.zeros((224, 224, 3), dtype=np.uint8),
    )

    frames = [np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(40)]
    progress = []
    preds = cnn.predict_frames(frames, progress_callback=lambda c: progress.append(c))

    assert len(preds) == 40
    assert set(preds[0].keys()) == {"age", "gender", "age_probs", "gender_confidence"}
    assert preds[0]["age"] == pytest.approx(27.5)
    assert preds[0]["gender"] == pytest.approx(1.0)
    assert len(preds[0]["age_probs"]) == 26
    assert preds[0]["gender_confidence"] == pytest.approx(0.88)
    # 진행률은 1..40 까지 보고된다(건너뛴 프레임 포함).
    assert progress[0] == 1
    assert progress[-1] == 40


def test_predict_frames_skips_unpreprocessable_frames(monkeypatch):
    """전처리(얼굴 검출)에 실패한 프레임은 건너뛴다."""
    state = {"i": 0}

    def fake_align(frame, target_size=cnn.MODEL_INPUT_SIZE):
        state["i"] += 1
        # 짝수 번째 프레임은 얼굴 검출 실패(None)로 처리
        if state["i"] % 2 == 0:
            return None
        return np.zeros((224, 224, 3), dtype=np.uint8)

    monkeypatch.setattr(cnn, "_get_cached_model", lambda model_path=None: (object(), "cpu"))
    monkeypatch.setattr(cnn, "_run_model", _fake_run_model)
    monkeypatch.setattr(cnn, "detect_and_align", fake_align)

    progress = []
    frames = [np.zeros((10, 10, 3), dtype=np.uint8) for _ in range(10)]
    preds = cnn.predict_frames(frames, progress_callback=lambda c: progress.append(c))

    assert len(preds) == 5  # 홀수 인덱스 5개만 성공
    assert progress[-1] == 10  # 건너뛴 프레임도 진행률에는 반영된다


def test_predict_frames_empty_returns_empty():
    assert cnn.predict_frames([]) == []


def test_predict_frames_propagates_critical_preprocessing_error(monkeypatch):
    """얼굴 미검출(None skip)과 달리, 치명적 전처리 예외는 빈 prediction으로 숨기지
    않고 그대로 전파되어야 한다(InferenceWorker.error_occurred 도달 보장)."""
    monkeypatch.setattr(cnn, "_get_cached_model", lambda model_path=None: (object(), "cpu"))

    def boom(frame, target_size=cnn.MODEL_INPUT_SIZE):
        raise RuntimeError("mediapipe import 실패")

    monkeypatch.setattr(cnn, "detect_and_align", boom)

    with pytest.raises(RuntimeError, match="mediapipe import 실패"):
        cnn.predict_frames([np.zeros((10, 10, 3), dtype=np.uint8)])


def test_expand_to_square_box_keeps_full_face_context():
    x1, y1, x2, y2 = cnn._expand_to_square_box(
        100, 80, 180, 180,
        image_width=320,
        image_height=240,
        margin=0.45,
    )

    assert x1 < 100
    assert y1 < 80
    assert x2 > 180
    assert y2 > 180
    assert (x2 - x1) == (y2 - y1)
    assert 0 <= x1 < x2 <= 320
    assert 0 <= y1 < y2 <= 240
