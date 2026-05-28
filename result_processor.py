"""
result_processor.py
===================
역할:
  모델팀으로부터 받은 40개의 예측 결과(dict)를
  이상치(나이 기준 위아래 2개씩) 제거 후 36개 평균 → 최종 결과 반환

입력 (predictions): 아래 4가지 키를 가진 dict 40개 리스트
  {
    "age"               : float        — 예측 나이
    "gender"            : float (0~1)  — 예측 성별
    "age_probs"         : list[float]  — 나이 확률분포 26개 (15~40세)
    "gender_confidence" : float        — 성별 확신도
  }

출력 (콜백): on_result_ready(result: dict)
  {
    "age"               : float  — 평균 나이
    "gender"            : int    — 0 또는 1
    "age_probs"         : list[float]  — 확률분포 평균 (26개)
    "gender_confidence" : float  — 성별 확신도 평균
  }

사용 예시:
  def 결과_전달(result):
      print(result["age"], result["gender"])

  process_predictions(predictions, on_result_ready=결과_전달)
"""

from typing import Callable, List


def process_predictions(
    predictions: List[dict],
    on_result_ready: Callable[[dict], None],
) -> None:
    """
    predictions    : 모델팀에서 받은 dict 리스트 (권장 40개)
    on_result_ready: 최종 결과 dict를 전달할 콜백
    """
    if len(predictions) == 0:
        print(f"[처리기] 오류: 예측값 없음")
        return

    if len(predictions) != 40:
        print(f"[처리기] 경고: 예측값 {len(predictions)}개 (기대값 40개)")

    n = len(predictions)

    # 전체 평균
    avg_age               = sum(p["age"]               for p in predictions) / n
    avg_gender            = sum(p["gender"]             for p in predictions) / n
    avg_gender_confidence = sum(p["gender_confidence"]  for p in predictions) / n

    # age_probs: 26개 원소 각각 평균
    probs_len = len(predictions[0]["age_probs"])
    avg_probs = [
        sum(p["age_probs"][i] for p in predictions) / n
        for i in range(probs_len)
    ]

    # 성별: 0.5 기준으로 0 또는 1 결정
    final_gender = 1 if avg_gender >= 0.5 else 0

    result = {
        "age"               : avg_age,
        "gender"            : final_gender,
        "age_probs"         : avg_probs,
        "gender_confidence" : avg_gender_confidence,
    }

    print(
        f"[처리기] 결과 → 나이: {avg_age:.1f}세 | "
        f"성별: {'여성(1)' if final_gender == 1 else '남성(0)'} "
        f"(원시값: {avg_gender:.3f}) | "
        f"성별확신도: {avg_gender_confidence*100:.1f}%"
    )
    on_result_ready(result)
