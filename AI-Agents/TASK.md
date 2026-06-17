# TASK

## TL;DR

- 목표: 첨부된 구버전 `main_window.py`의 GUI 디자인 변경 방향을 참고해 현재 GUI 화면의 시각 디자인만 갱신한다.
- 핵심 제한: 현재 출력/추론/집계 로직은 바꾸지 않는다. 특히 나이 확신도 계산은 현행 표준편차 기반 공식을 유지한다.
- 첨부 파일 주의: 첨부 코드는 예전 버전이라 나이 확신도 판단 방식이 현재와 다르다. 코드 전체를 복사하지 말고 스타일/레이아웃 참고 자료로만 사용한다.
- 수정 가능 범위: 원칙적으로 `src/face_age_gender_predictor/app/main_window.py`의 View/UI 스타일 및 레이아웃. 테스트 보강이 필요하면 GUI 표시 테스트만 최소 수정한다.
- 추가 CI 주의: GitHub Actions에서 `tests/test_result_processor.py::test_age_and_gender_confidence_averages_preserved_with_gender_change`가 float 경계값 문제로 실패한 기록이 있다. 디자인 작업자는 이를 기존 로직 보존 조건의 일부로 확인하고, 필요하면 최소 수정으로 안정화한다.
- 이전 작업 상태: 이전 `AI-Agents/REVIEW.md` Verdict는 `PASS`이며, 이전 작업 기록은 `AI-Agents/archive/2026-06-18-age-confidence-stddev-pass/` 아래에 보존되어 있다.

## Goal

현재 GUI의 기능과 결과 표시 로직은 유지하면서, 첨부된 구버전 GUI 코드가 보여주는 밝은 블루/화이트 계열의 화면 디자인을 현재 코드에 맞게 반영한다.

이 작업은 **디자인 포팅 작업**이다. 모델 추론 결과, 나이 확신도 계산, 성별 집계, 결과 processor, 버튼 동작, 카메라 흐름, 스레드/타이머 동작을 변경하는 작업이 아니다.

다만 GitHub Actions에서 이미 확인된 `result_processor` 성별 평균 경계값 테스트 실패는 이번 작업 전/중에 반드시 정리되어야 한다. 이 수정은 정책 변경이 아니라 기존 정책(`average_gender >= 0.5 -> 1`)을 CI 환경에서도 안정적으로 보장하기 위한 최소 안정화로만 허용한다.

## Previous Task Status

- 이전 작업 `REVIEW.md` Verdict: `PASS`.
- 이전 작업 `PR.md`, `REVIEW.md`, `TASK.md`, `ACCEPTANCE.md`, `IMPLEMENTATION.md`는 archive 아래에 보존되었다.
- 이전 작업에서 확정된 현행 로직은 이번 작업에서 유지해야 한다.
  - 나이 확신도: 26-bin 나이 분포의 weighted standard deviation 기반 confidence.
  - invalid `age_probs`: 높은 confidence로 fallback하지 않고 unavailable 상태로 표시.
  - 성별 표시 contract: 앱 내부 downstream 기준 `gender == 1 -> 여성`, `gender == 0 -> 남성`.
- `result_processor` 성별 최종 집계: 유효 prediction의 `gender` 평균이 `>= 0.5`이면 `1`, `< 0.5`이면 `0`.
- GitHub CI에서 `0.1 * 20 + 0.9 * 20`처럼 수학적으로 평균이 `0.5`인 테스트가 부동소수점 합산 오차로 `0` 판정될 수 있음이 확인되었다. 이 경계값 안정성은 유지/보강해야 한다.

## Background

사용자가 첨부한 파일은 GUI 디자인 변경사항이 들어 있는 구버전 `main_window.py`다. 이 파일은 다음과 같은 시각 방향을 가진다.

- 밝은 블루/화이트 계열 배경.
- 카드형 섹션과 옅은 border.
- 파란색 primary 버튼/진행 표시.
- 더 compact한 측정/결과 패널.
- 얼굴 preview 영역, 결과 metric 카드, histogram 영역의 시각 정리.
- 결과 상세 정보의 2-column grid 느낌.
- light theme에 맞춘 histogram bar 색상과 result card 스타일.

단, 첨부 파일은 현재 코드보다 오래된 버전이라 현재 프로젝트의 나이 확신도 정책과 다르다. 첨부 파일에 있는 예측 나이 주변 확률 질량 방식, 예전 result 표시 흐름, 예전 helper signature를 현재 코드에 그대로 가져오면 안 된다.

## Required Implementation

### 1. 디자인만 반영

구현자는 현재 `src/face_age_gender_predictor/app/main_window.py`를 먼저 읽고, 현행 함수 구조와 결과 표시 흐름을 기준으로 첨부 파일의 디자인 요소만 선별 반영한다.

반영 가능한 예:

- window/background 색상.
- QLabel/QFrame/QPushButton/QProgressBar/QGroupBox 등 widget style sheet.
- 카드/패널 border, radius, padding, spacing.
- preview image frame 크기와 alignment.
- result metric card의 시각 배치.
- histogram widget의 색상, 높이, 여백, label 표시 방식.
- 측정 진행률과 버튼 상태의 visual style.
- 텍스트 크기, weight, color 같은 presentation 속성.
- 레이아웃 spacing/margin 조정.

반영하면 안 되는 예:

- 나이 확신도 계산 공식 변경.
- `age_probs` 해석 방식 변경.
- histogram 값 생성 로직 변경.
- result dict contract 변경.
- 성별 label mapping 변경.
- 성별 집계 threshold 변경.
- camera/worker/thread/timer/signal-slot 흐름 변경.
- `result_processor.py`의 집계 로직 변경.
- 모델 inference 코드 변경.

### 2. 현재 나이 확신도 로직 유지

현재 GUI는 이전 작업에서 표준편차 기반 나이 확신도 공식을 갖도록 정리되었다. 이번 디자인 작업 후에도 다음이 유지되어야 한다.

- age bin은 `15..40` inclusive, 총 26개 class로 해석한다.
- 26-bin 나이 분포의 weighted standard deviation을 계산한다.
- 표준편차 `1.57 -> 99%`, `8.23 -> 1%` inverse linear mapping을 유지한다.
- valid confidence는 `[1%, 99%]` 범위로 clamp한다.
- invalid `age_probs`는 높은 confidence로 fallback하지 않는다.
- invalid `age_probs` 표시 정책은 현행처럼 unavailable/`-` 계열로 유지한다.
- 히스토그램이 valid distribution일 때만 안전하게 표시되어야 한다.

첨부 파일에 `_compute_age_confidence(age_probs, predicted_age)`처럼 예측 나이 주변 확률을 합산하는 방식이 있더라도, 이 방식은 이번 작업에서 사용하지 않는다.

### 3. 현재 성별/결과 로직 유지

이번 작업은 성별 로직을 바꾸지 않는다.

- GUI 표시 contract는 `gender == 1 -> 여성`, `gender == 0 -> 남성`을 유지한다.
- `gender_confidence` 표시/평균 정책은 변경하지 않는다.
- `result_processor`의 최종 성별 집계 방식은 변경하지 않는다.
- 유효 prediction 30개 미만 실패 조건은 변경하지 않는다.
- age 평균 집계 방식은 변경하지 않는다.

만약 디자인 포팅 과정에서 result label을 다시 작성해야 한다면, 표시 텍스트의 시각 스타일만 바꾸고 값 계산/분기 조건은 현행 코드를 그대로 유지한다.

### 3-1. GitHub CI 성별 threshold 경계값 안정화

GitHub Actions 실패 사례:

```text
FAILED tests/test_result_processor.py::test_age_and_gender_confidence_averages_preserved_with_gender_change
assert result["gender"] == 1
실제 result["gender"] == 0
로그상 avg_gender는 0.500으로 보이나, 내부 float 값이 0.5보다 미세하게 작아진 것으로 추정
```

요구사항:

- `average_gender >= 0.5 -> gender == 1` 정책을 변경하지 않는다.
- 수학적으로 평균이 `0.5`인 입력은 CI 환경에서도 안정적으로 `gender == 1`이 되어야 한다.
- 가능한 최소 수정은 `result_processor.py`에서 `gender` 평균 계산을 `math.fsum` 기반으로 안정화하는 것이다.
- 필요하면 `avg_age`, `avg_gender_confidence`도 동일하게 `math.fsum`으로 계산해 평균 집계 안정성을 높일 수 있다.
- 이 변경은 성별 정책 변경이 아니라 기존 정책의 numeric stability fix로 기록한다.
- 테스트를 policy와 분리해 더 안정적으로 만들 수도 있지만, `average_gender == 0.5` 경계 테스트는 반드시 유지한다.
- 이 CI fix를 수행할 경우 `AI-Agents/IMPLEMENTATION.md`에 원인, 수정 방식, GitHub CI 실패 재현/해결 기준을 기록한다.

### 4. Layout / UX Requirements

구현자는 첨부 디자인의 방향을 현재 앱에 맞게 적용하되, 다음 UX 조건을 지킨다.

- 앱 실행 직후 화면에서 주요 영역이 겹치지 않아야 한다.
- 버튼 텍스트, 결과 텍스트, progress 텍스트가 parent 영역 밖으로 넘치지 않아야 한다.
- 카메라 preview 또는 얼굴 preview 영역의 비율이 깨지지 않아야 한다.
- 측정 전/측정 중/성공/실패 상태에서 버튼 enable/disable 상태가 기존과 동일해야 한다.
- 실패 메시지가 표시되어도 앱이 멈추지 않고 다시 측정 가능한 상태로 돌아와야 한다.
- histogram이 너무 어둡거나 배경과 구분되지 않는 상태가 아니어야 한다.
- 작은 창 크기에서도 주요 결과 값이 겹치지 않아야 한다.

### 5. Tests / Verification

자동 테스트가 이미 GUI helper와 표시 로직을 확인한다면, 디자인 변경 때문에 깨진 테스트만 현재 로직 기준으로 갱신한다.

필요 시 다음 검증을 수행한다.

- `python -m py_compile`로 `main_window.py` 문법 확인.
- 관련 GUI 테스트가 있다면 `tests/test_main_window.py` 실행.
- GitHub CI 실패가 있었던 `tests/test_result_processor.py`를 실행한다.
- 전체 pytest가 과하지 않으면 전체 테스트 실행.
- GUI 실행이 가능한 환경이면 수동 smoke로 화면 겹침, 버튼 상태, 성공/실패 결과 표시 확인.

테스트를 추가/수정할 때도 로직 기대값은 현행 표준편차 기반 나이 확신도와 현행 성별 contract를 기준으로 한다. 첨부 파일의 구버전 기대값을 테스트에 넣지 않는다.

## Target Files

수정 가능 파일:

- `src/face_age_gender_predictor/app/main_window.py`
- `tests/test_main_window.py` 또는 기존 GUI 표시 테스트 파일, 필요한 경우에 한함
- `src/face_age_gender_predictor/processing/result_processor.py`는 원칙적으로 수정 금지이나, GitHub CI의 `average_gender == 0.5` float 경계 실패를 해결하기 위한 numeric stability 최소 수정은 허용
- `tests/test_result_processor.py`는 위 CI 실패 검증/보강이 필요한 경우에 한해 최소 수정 가능
- `AI-Agents/IMPLEMENTATION.md`

읽기/참조 가능 파일:

- 첨부된 구버전 GUI 코드
- `src/face_age_gender_predictor/processing/result_processor.py`
- `tests/test_result_processor.py`
- `docs/spec.md` 또는 `docs/SPEC.md`, 존재하는 경우 관련 GUI/결과 표시 섹션
- `docs/development.md`

수정하지 말 것:

- `src/face_age_gender_predictor/processing/result_processor.py`의 정책/구조 변경
- `src/face_age_gender_predictor/inference/*`
- 모델 파일과 학습 코드
- `.env`, `.env.*`
- `models/*.pt`, `models/*.pth`, `models/*.onnx`
- 개인 이미지, 대용량 산출물, build/cache 산출물
- GitHub PR 본문
- `AI-Agents/PR.md` (Codex Release 담당이 따로 작성)

## Out of Scope

- 나이 확신도 공식 재설계.
- 성별 confidence 또는 성별 집계 변경.
- 모델 inference output contract 변경.
- `result_processor` 구조 변경.
- `result_processor` 성별 threshold 정책 변경. 단, `average_gender >= 0.5 -> 1`을 안정적으로 보장하기 위한 float 합산 안정화는 허용.
- QThread/카메라 pipeline 변경.
- 새 기능 추가.
- 실제 모델 성능 평가.
- Git commit, push, PR 생성.

## Notes For Claude Code

- 첨부 파일은 "디자인 참고 자료"이지 "교체할 정답 코드"가 아니다.
- 현재 `main_window.py`의 로직을 기준으로, 스타일/레이아웃만 필요한 만큼 이식하라.
- 특히 `_compute_age_confidence` 또는 age confidence 관련 helper를 구버전 코드로 되돌리지 말라.
- 구현 후 `AI-Agents/IMPLEMENTATION.md`에 어떤 디자인 요소를 반영했는지, 어떤 로직을 의도적으로 유지했는지, 실행한 테스트와 미검증 항목을 기록하라.
- GitHub CI에서 실패한 `test_age_and_gender_confidence_averages_preserved_with_gender_change`를 반드시 확인하라. 실패 원인은 디자인이 아니라 float 경계값 안정성 문제이며, 정책 변경 없이 최소 수정으로 해결하라.
- 코드 변경 전에 현재 테스트가 어떤 로직을 보호하는지 확인하고, 디자인 변경으로 인한 테스트 수정은 최소화하라.
