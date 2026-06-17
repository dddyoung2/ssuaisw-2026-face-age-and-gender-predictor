# TASK

## TL;DR

- 목표: GUI의 나이 확신도 표시를 현재 방식에서 "결과 히스토그램/logit 분포의 표준편차 기반 보정 confidence"로 변경한다.
- 배경 요청: test data 검증을 통해 실효 표준편차 범위 `1.57 ~ 8.23`을 얻었고, 실제 프로그램 실행 시 결과 히스토그램(logit)에서 표준편차를 추출해 `1.57`에 가까우면 `99%`, `8.23`에 가까우면 `1%`로 표시하고 싶다.
- 범위: 나이 confidence 계산 함수, 결과 표시 경로, `result_processor` 성별 최종 집계 기준 명확화, 필요한 테스트, 구현 보고서 작성.
- 수정 금지: 모델 파일, 학습 로직, gender confidence, UI 대규모 리디자인, GitHub PR 문서.
- 이전 작업 상태: 이전 `REVIEW.md` Verdict는 `PASS`이며, 이전 작업 기록은 `AI-Agents/archive/2026-06-18-model-integration-pass/` 아래에 보존되어 있다.

## Goal

현재 GUI의 "나이 확신도"는 모델이 반환한 `age_probs`를 사용하지만, 이전 작업에서는 예측 나이 주변 확률 질량 같은 휴리스틱으로 표시될 수 있었다. 이번 작업의 목표는 이를 명시적인 표준편차 기반 보정 공식으로 교체하는 것이다.

사용자가 보는 나이 확신도는 다음 원칙을 따라야 한다.

```text
age distribution이 좁고 표준편차가 1.57에 가까움 -> 높은 확신도, 최대 99%
age distribution이 넓고 표준편차가 8.23에 가까움 -> 낮은 확신도, 최소 1%
```

즉, 모델의 나이 histogram/logit/probability 분포가 얼마나 퍼져 있는지를 weighted standard deviation으로 계산하고, 이를 calibrated inverse linear mapping으로 confidence percent에 대응시킨다.

## Previous Task Status

- 이전 `AI-Agents/REVIEW.md` Verdict: `PASS`.
- 이전 작업의 `TASK.md`, `ACCEPTANCE.md`, `IMPLEMENTATION.md`, `REVIEW.md`, `PR.md`는 archive 아래에 복사해 보존했다.
- 이번 TASK는 이전 모델 연결/반복 측정 작업을 다시 구현하는 작업이 아니다.
- 이번 TASK는 나이 확신도 표시 정책을 교체하고, `result_processor`의 성별 최종 집계 기준을 문서/구현/테스트에서 일관되게 명확화하는 좁은 후속 작업이다.

## Current Behavior To Replace

구현자는 현재 코드에서 실제 사용 중인 나이 확신도 계산 위치를 먼저 확인해야 한다. 후보 위치:

- `src/face_age_gender_predictor/app/main_window.py`
- `AgeEstimatorWindow` 안의 age confidence 계산/표시 함수
- result slot에서 `age_probs` 또는 histogram 값을 받아 preview/result label에 표시하는 경로

이전 작업 기록에는 `AgeEstimatorWindow._compute_age_confidence()`가 예측 나이 `±2`세 구간의 probability mass를 합산하는 방식으로 언급되어 있다. 이번 작업에서는 이 방식이 남아 있다면 제거하거나 더 이상 사용하지 않도록 해야 한다.

## Required Formula

### 입력 분포

나이 분포는 26개 bin이어야 하며, 나이는 `15`부터 `40`까지 inclusive다.

```python
ages = [15, 16, 17, ..., 40]
```

입력으로 사용할 수 있는 값:

- normalized `age_probs`: 합이 1에 가까운 probability list
- unnormalized probability-like weights: 합이 0보다 크면 normalize해서 사용 가능
- raw logits: 명확히 logit으로 전달되는 값이면 softmax로 probability 변환 후 사용

구현자는 현재 result dict에서 전달되는 필드가 `age_probs`인지, raw logits인지 먼저 확인한다. 현재 문서 기준 prediction/result dict는 `age_probs`를 사용한다.

### 표준편차 계산

분포를 normalize한 뒤 weighted mean과 weighted standard deviation을 계산한다.

```text
weights = normalized probabilities over ages 15..40
mean = sum(weights[i] * ages[i])
stddev = sqrt(sum(weights[i] * (ages[i] - mean)^2))
```

### confidence mapping

아래 상수를 사용한다.

```text
STDDEV_BEST = 1.57
STDDEV_WORST = 8.23
CONFIDENCE_BEST = 99.0
CONFIDENCE_WORST = 1.0
```

표준편차가 낮을수록 confidence가 높다.

```text
ratio = (stddev - STDDEV_BEST) / (STDDEV_WORST - STDDEV_BEST)
confidence = CONFIDENCE_BEST - ratio * (CONFIDENCE_BEST - CONFIDENCE_WORST)
```

최종 confidence는 valid distribution에 대해 `[1.0, 99.0]`로 clamp한다.

```text
stddev <= 1.57 -> 99%
stddev >= 8.23 -> 1%
```

### invalid input policy

다음 입력은 높은 confidence를 만들면 안 된다.

- `None`
- empty list
- 길이가 26이 아닌 list
- 숫자가 아닌 값 포함
- NaN/Inf 포함
- normalize할 수 없는 분포
- 합이 0 이하인 weight 분포

이 경우 GUI에는 `0.0%`, `-`, 또는 명확한 unavailable 상태를 표시한다. 기존 UI 관례에 맞추되, 절대 99% 같은 높은 confidence로 fallback하지 않는다.

## Requirements

### 1. Age Confidence 계산 정책 변경

- 예측 나이 `±2`세 probability mass 방식은 더 이상 displayed age confidence에 사용하지 않는다.
- displayed age confidence는 26-bin 나이 분포의 weighted standard deviation으로 계산한다.
- `age_probs`가 이미 normalized probability면 검증 후 사용한다.
- `age_probs`가 unnormalized weight면 합이 0보다 클 때 normalize한다.
- raw logits를 별도 필드로 사용하게 된다면 softmax 후 사용한다. 단, 현재 result contract를 임의로 바꾸지 않는다.
- age bin은 반드시 `15..40`의 26개 class로 해석한다.
- standard deviation `1.57`은 `99%`로 매핑한다.
- standard deviation `8.23`은 `1%`로 매핑한다.
- calibrated range 밖의 valid distribution은 `[1%, 99%]`로 clamp한다.
- invalid distribution은 high confidence가 아닌 unavailable/0% 계열로 표시한다.
- gender confidence 계산과 표시는 변경하지 않는다.
- 나이 히스토그램 시각화 자체는 유지한다.

### 2. result_processor 성별 최종 집계 기준 명확화

현재 prediction dict의 `gender` 값은 프레임별 성별 예측 점수로 사용한다. 구현자는 `src/face_age_gender_predictor/processing/result_processor.py`와 관련 테스트/문서가 아래 기준과 일치하는지 확인하고, 다르면 최소 수정한다.

현재 코드 검토 기준:

- `src/face_age_gender_predictor/processing/result_processor.py`의 출력 로그는 `final_gender == 1`을 `여성(1)`, `final_gender == 0`을 `남성(0)`으로 표시한다.
- `src/face_age_gender_predictor/app/main_window.py`의 GUI 결과 표시도 `gender == 1`이면 `"여성"`, 그 외 `0`이면 `"남성"`으로 표시한다.
- 따라서 현재 앱의 downstream label contract는 `gender == 1 -> 여성`, `gender == 0 -> 남성`이다.
- 다만 `src/face_age_gender_predictor/inference/CNNmodel.py`는 모델의 `predicted_gender` 출력을 그대로 prediction dict의 `gender` float으로 전달한다. 모델 자체가 실제로 `1=여성`, `0=남성` label로 학습/출력하는지는 코드만으로 완전히 보장되지 않는다.
- 구현자는 이번 task에서 앱 내부 문서/테스트/표시 로직이 `1=여성`, `0=남성` contract와 일관되는지 확인하고, 모델 label contract가 불확실하면 `AI-Agents/IMPLEMENTATION.md`의 Not Verified 또는 Follow-up에 기록한다.

- 유효 prediction만 필터링한 뒤 집계한다.
- 기존 age 평균 집계 방식은 유지한다.
- 기존 `gender_confidence` 평균 집계 방식은 유지한다.
- 유효 prediction이 30개 미만이면 실패 처리하는 기존 조건은 유지한다.
- 최종 gender는 유효 prediction들의 `gender` score 평균값으로 결정한다.
- `average_gender >= 0.5`이면 최종 `gender`는 `1`, 즉 `여성`이다.
- `average_gender < 0.5`이면 최종 `gender`는 `0`, 즉 `남성`이다.
- `gender` score가 누락되었거나 유효하지 않은 prediction은 기존 유효 prediction 필터링 정책과 일관되게 처리한다.
- 이 기준은 `TASK.md`, `ACCEPTANCE.md`, `IMPLEMENTATION.md`, 테스트 코드, 필요한 경우 `docs/SPEC.md` 또는 관련 문서에서 서로 모순되지 않아야 한다.
- 관련 테스트가 없으면 추가하고, 이미 있으면 threshold 경계값을 포함하도록 보강한다.

테스트에서 확인할 핵심 케이스:

- 모든 유효 prediction의 평균 `gender`가 `0.5` 이상이면 최종 `gender == 1`.
- 평균 `gender`가 `0.5` 미만이면 최종 `gender == 0`.
- 평균이 정확히 `0.5`이면 최종 `gender == 1`.
- GUI 표시 경로는 `gender == 1`을 `여성`, `gender == 0`을 `남성`으로 표시한다.
- `age` 평균 집계 결과는 기존 방식과 동일하게 유지된다.
- `gender_confidence` 평균 집계 결과는 기존 방식과 동일하게 유지된다.
- 유효 prediction이 30개 미만이면 성별 threshold와 무관하게 실패 result가 유지된다.

### 3. 코드 위치와 구조

- 가능하면 나이 confidence 계산을 작은 pure helper 함수로 분리한다.
- helper는 GUI 상태에 강하게 의존하지 않아야 하며 테스트하기 쉬워야 한다.
- 이미 `AgeEstimatorWindow._compute_age_confidence()` 같은 함수가 있다면, 그 함수 내부를 새 공식으로 교체해도 된다.
- result dict contract를 넓히지 않아도 구현 가능한 경우 나이 confidence 때문에 `result_processor.py`를 수정하지 않는다.
- 다만 성별 최종 집계 기준이 위 요구사항과 다르다면 `result_processor.py`를 수정 대상에 포함한다.
- raw logit 지원이 꼭 필요하다고 판단되는 경우에도 기존 `age_probs` contract를 깨지 말고 최소 변경만 한다.

### 4. GUI 표시

- 성공 result 표시 시 새 confidence 값이 사용되어야 한다.
- 표시 포맷은 기존 UI와 맞춰 percentage로 유지한다.
- 예: `87.32%`, `99.00%`, `1.00%` 등 기존 표시 자릿수와 조화를 맞춘다.
- invalid input이면 기존 UI 관례에 맞춰 `-`, `0.00%`, 또는 실패 메시지를 표시한다.
- age histogram bar rendering은 기존대로 유지한다.

### 5. Tests

다음 테스트를 추가하거나 기존 테스트를 갱신한다.

- stddev `1.57`에 해당하는 분포가 `99%`로 매핑된다.
- stddev `8.23`에 해당하는 분포가 `1%`로 매핑된다.
- stddev가 `1.57`보다 작으면 `99%`로 clamp된다.
- stddev가 `8.23`보다 크면 `1%`로 clamp된다.
- uniform distribution over ages `15..40`은 낮은 confidence를 만든다.
- invalid input은 높은 confidence를 만들지 않는다.
- 기존 `±2`세 probability mass 방식에 의존하는 테스트가 있다면 제거하거나 새 공식 기준으로 다시 작성한다.
- GUI result slot 또는 helper를 통해 실제 표시 경로가 새 계산을 사용하는지 확인한다.
- `result_processor`에서 유효 prediction의 `gender` 평균이 `0.5` 이상이면 최종 `gender`가 `1`이 되는지 확인한다.
- `result_processor`에서 유효 prediction의 `gender` 평균이 `0.5` 미만이면 최종 `gender`가 `0`이 되는지 확인한다.
- `result_processor`에서 평균 `gender == 0.5` 경계값이 최종 `gender == 1`로 처리되는지 확인한다.
- GUI 표시 테스트 또는 코드 검토로 `gender == 1 -> 여성`, `gender == 0 -> 남성` contract가 유지되는지 확인한다.
- 성별 집계 변경 후에도 age 평균, `gender_confidence` 평균, 유효 prediction 30개 미만 실패 조건이 유지되는지 확인한다.

테스트 데이터 생성 팁:

- 정확히 원하는 stddev를 가진 분포를 만들기 어렵다면, helper 함수 레벨에서는 standard deviation을 confidence로 변환하는 작은 함수도 분리해 endpoint mapping을 직접 테스트할 수 있다.
- distribution -> stddev 계산 테스트와 stddev -> confidence mapping 테스트를 나누면 테스트가 더 안정적이다.

## Target Files

수정 가능 파일:

- `src/face_age_gender_predictor/app/main_window.py`
- `src/face_age_gender_predictor/processing/result_processor.py`
- `tests/test_main_window.py`
- `tests/test_result_processor.py`
- 필요 시 `tests/conftest.py`
- `AI-Agents/IMPLEMENTATION.md`

읽기/참조 권장 파일:

- `docs/SPEC.md`
- `docs/components.md`
- `src/face_age_gender_predictor/inference/CNNmodel.py`

수정하지 말 것:

- `.env`, `.env.*`
- `models/*.pt`, `models/*.pth`, `models/*.onnx`
- 개인 이미지 또는 대용량 산출물
- GitHub PR 본문
- `AI-Agents/PR.md` (Codex Release 담당이 따로 작성)
- 모델 학습 코드 또는 모델 weight
- gender confidence 정책
- 광범위한 UI 리디자인

## Out of Scope

- 모델 재학습
- 모델 output shape 변경
- gender confidence 변경
- age 평균 집계 방식 변경
- 유효 prediction 30개 미만 실패 조건 변경
- age class 범위 변경
- result dict의 breaking change
- 실제 웹캠 end-to-end QA 수행
- Git commit, push, PR 생성

## Notes For Claude Code

- 이 task는 좁은 수식 교체 작업이다. 이전 모델 연결/반복 측정 PASS 작업을 다시 건드리지 말라.
- 구현 전 현재 age confidence 계산 경로를 먼저 찾아라.
- 변경은 계산 helper, 표시 연결, 테스트에 집중하라.
- `result_processor`를 건드릴 경우 성별 최종 threshold만 명확히 하고, age 평균/gender_confidence 평균/30개 미만 실패 조건은 유지하라.
- 확률 분포가 invalid일 때 high confidence로 fallback하지 않는 것이 핵심 방어 조건이다.
- 완료 후 `AI-Agents/IMPLEMENTATION.md`에 변경 파일, 공식, 테스트 결과, 남은 미검증 사항을 기록하라.
