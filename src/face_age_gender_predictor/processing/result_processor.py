"""
result_processor.py
===================
역할:
  모델팀으로부터 받은 40개의 예측 결과(dict)를 집계해 최종 result dict로 반환한다.
  유효 prediction 수가 기준 이상이면 성공, 미만이면 실패로 처리한다.

입력 (predictions): 아래 4가지 키를 가진 dict 리스트 (권장 40개)
  {
    "age"               : float        — 예측 나이
    "gender"            : float (0~1)  — 예측 성별 원시값
    "age_probs"         : list[float]  — 나이 확률분포 26개 (15~40세)
    "gender_confidence" : float        — 성별 확신도
  }

출력 (콜백): on_result_ready(result: dict)
  성공:
  {
    "success"           : True,
    "age"               : float,
    "gender"            : int,           # 0 또는 1
    "age_probs"         : list[float],   # 확률분포 평균 (26개)
    "gender_confidence" : float,
    "valid_count"       : int,
    "reason"            : None,
  }
  실패:
  {
    "success"           : False,
    "age"               : None,
    "gender"            : None,
    "age_probs"         : None,
    "gender_confidence" : None,
    "valid_count"       : int,
    "reason"            : str,           # 예: "valid_count_below_30"
  }

사용 예시:
  def 결과_전달(result):
      if result["success"]:
          print(result["age"], result["gender"])
      else:
          print("실패:", result["reason"])

  process_predictions(predictions, on_result_ready=결과_전달)
"""

import math
from typing import Callable, List, Optional

# 유효 prediction이 이 값 이상이어야 성공으로 본다. (docs/SPEC.md S6 기준)
MIN_VALID_PREDICTIONS = 30


def _is_valid_prediction(prediction: dict) -> bool:
    """result 집계에 사용할 수 있는 prediction인지 검사한다."""
    if not isinstance(prediction, dict):
        return False

    age = prediction.get("age")
    gender = prediction.get("gender")
    age_probs = prediction.get("age_probs")
    gender_confidence = prediction.get("gender_confidence")

    if age is None or gender is None or gender_confidence is None:
        return False

    if not isinstance(age_probs, (list, tuple)) or len(age_probs) == 0:
        return False

    return True


def _build_failure(valid_count: int, reason: str) -> dict:
    """GUI가 표시하기 쉬운 실패 result dict를 만든다."""
    return {
        "success": False,
        "age": None,
        "gender": None,
        "age_probs": None,
        "gender_confidence": None,
        "valid_count": valid_count,
        "reason": reason,
    }


def process_predictions(
    predictions: List[dict],
    on_result_ready: Callable[[dict], None],
) -> Optional[dict]:
    """
    predictions    : 모델팀에서 받은 dict 리스트 (권장 40개)
    on_result_ready: 최종 result dict를 전달할 콜백

    반환값: 전달한 result dict (테스트 편의를 위해 콜백과 동일한 dict를 반환)
    """
    valid = [p for p in (predictions or []) if _is_valid_prediction(p)]
    valid_count = len(valid)

    if valid_count < MIN_VALID_PREDICTIONS:
        reason = "no_predictions" if valid_count == 0 else "valid_count_below_30"
        result = _build_failure(valid_count, reason)
        print(
            f"[처리기] 실패 → 유효 예측 {valid_count}개 "
            f"(기준 {MIN_VALID_PREDICTIONS}개) | reason: {reason}"
        )
        on_result_ready(result)
        return result

    n = valid_count

    # 유효 prediction 전체 평균.
    # math.fsum으로 부동소수점 합산 오차를 줄여 평균 집계를 안정화한다.
    # (수학적으로 평균이 정확히 0.5인 gender 입력이 일반 sum의 누적 오차로 0.5보다
    #  미세하게 작아져 `>= 0.5` 경계에서 0으로 잘못 판정되는 CI 실패를 방지한다.
    #  정책은 그대로이고 numeric stability만 보강한다.)
    avg_age = math.fsum(p["age"] for p in valid) / n
    avg_gender = math.fsum(p["gender"] for p in valid) / n
    avg_gender_confidence = math.fsum(p["gender_confidence"] for p in valid) / n

    # age_probs: 원소별 평균
    probs_len = len(valid[0]["age_probs"])
    avg_probs = [
        sum(p["age_probs"][i] for p in valid) / n
        for i in range(probs_len)
    ]

    # 성별: 평균 원시값 0.5 기준으로 0 또는 1 결정
    final_gender = 1 if avg_gender >= 0.5 else 0

    result = {
        "success": True,
        "age": avg_age,
        "gender": final_gender,
        "age_probs": avg_probs,
        "gender_confidence": avg_gender_confidence,
        "valid_count": valid_count,
        "reason": None,
    }

    print(
        f"[처리기] 성공 → 나이: {avg_age:.1f}세 | "
        f"성별: {'여성(1)' if final_gender == 1 else '남성(0)'} "
        f"(원시값: {avg_gender:.3f}) | "
        f"성별확신도: {avg_gender_confidence * 100:.1f}% | "
        f"유효 예측: {valid_count}개"
    )
    on_result_ready(result)
    return result
