# -*- coding: utf-8 -*-
"""AgeEstimatorWindow 측정 얼굴 미리보기 표시 테스트 (재측정 회귀).

Codex QA가 보고한 버그: 첫 측정 성공 후 재감지 → 측정 버튼 재활성화 → 사용자가
다시 측정 → 다음 결과에서 결과 값은 나오지만 측정된 얼굴 사진 영역이 빈/오래된 상태로
남는 경우가 있다. 캡처 종료 후 재개되는 감지 루프가 live 프레임을 덮어써도, 이번
측정에서 고정한 캡처 스냅샷으로 결과 얼굴이 갱신되어야 한다.

qapp 픽스처는 tests/conftest.py(세션 단위 offscreen QApplication)에서 제공된다.
"""

import numpy as np

from face_age_gender_predictor.app.main_window import AgeEstimatorWindow


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


def _frame_with_box():
    # 480x640 더미 프레임 + 프레임 안에 들어가는 유효 face_box (x, y, w, h)
    return np.zeros((480, 640, 3), dtype=np.uint8), (100, 100, 200, 200)


def _run_one_measurement(window):
    """카운트다운 → 얼굴 프레임 → 캡처 → 분석 → 성공 결과 흐름을 모사한다."""
    window.on_state_changed("COUNTDOWN")          # 새 측정 시작: 이전 미리보기/스냅샷 초기화
    frame, box = _frame_with_box()
    window.on_preview_frame((frame, box))         # 카운트다운 중 얼굴 프레임 → 스냅샷 고정
    window.on_state_changed("CAPTURING")          # 캡처(프리뷰 일시 정지 구간)
    # 캡처 종료 후 재개된 감지 루프가 live 프레임을 얼굴 없음으로 덮어쓰는 상황을 모사
    window.on_state_changed("ANALYZING")
    window.on_preview_frame((np.zeros((480, 640, 3), dtype=np.uint8), None))
    window.on_result_ready(_success_result())     # 결과 표시: 고정 스냅샷으로 얼굴 갱신


def test_first_measurement_shows_captured_face(qapp):
    window = AgeEstimatorWindow()
    window.camera_running = True
    window.face_ready = True

    _run_one_measurement(window)

    assert not window.preview_face_label.pixmap().isNull()
    assert window.preview_face_label.text() == ""


def test_second_measurement_updates_captured_face_after_redetect(qapp):
    window = AgeEstimatorWindow()
    window.camera_running = True
    window.face_ready = True

    # 1차 측정 성공 → 얼굴 사진 표시
    _run_one_measurement(window)
    assert not window.preview_face_label.pixmap().isNull()

    # 측정 완료 후 자동 재감지 → 얼굴 다시 준비됨 (이전 결과/사진은 유지되어야 함)
    window.on_state_changed("IDLE")
    window.on_face_ready_changed(True)
    assert not window.preview_face_label.pixmap().isNull()  # 재감지가 사진을 지우지 않음

    # 2차 측정: 재활성화된 버튼으로 시작 → 다음 결과에서 캡처 얼굴이 갱신되어야 함
    _run_one_measurement(window)

    assert not window.preview_face_label.pixmap().isNull()
    assert window.preview_face_label.text() == ""
