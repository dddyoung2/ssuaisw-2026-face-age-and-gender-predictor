# IMPLEMENTATION

## Summary

GUI의 "나이 확신도(age confidence)" 표시 공식을 기존 예측 나이 ±2세 probability mass
방식에서 **26-bin(15~40세) 나이 분포의 weighted standard deviation 기반 보정 confidence**로
교체했다. 표준편차 `1.57 → 99%`, `8.23 → 1%`의 inverse linear mapping을 적용하고, 유효하지
않은 분포는 높은 confidence로 fallback하지 않고 `-`(unavailable)로 표시한다.

또한 `result_processor`의 성별 최종 집계 기준이 TASK 요구사항(유효 prediction의 gender
score 평균, `>= 0.5 → 1(여성)`, `< 0.5 → 0(남성)`, age 평균/gender_confidence 평균/
valid_count < 30 실패 유지)과 이미 일치함을 확인했고, 경계값 포함 테스트를 보강했다.
`result_processor.py` 코드 자체는 수정이 필요 없어 변경하지 않았다.

이번 작업은 좁은 수식 교체 + 성별 집계 기준 명확화 범위이며, 이전 모델 연결/반복 측정
PASS 작업은 다시 건드리지 않았다.

## Changed Files

- `src/face_age_gender_predictor/app/main_window.py`
  - 모듈 레벨 pure helper 추가: `age_distribution_stddev()`, `age_confidence_from_stddev()`,
    `age_confidence_percent()` 및 상수
    (`AGE_CONF_STDDEV_BEST=1.57`, `AGE_CONF_STDDEV_WORST=8.23`,
    `AGE_CONF_CONFIDENCE_BEST=99.0`, `AGE_CONF_CONFIDENCE_WORST=1.0`,
    `AGE_CONF_BIN_COUNT=26`, `AGE_CONF_AGE_MIN=15`).
  - `AgeEstimatorWindow._compute_age_confidence(age_probs)`를 새 공식으로 교체
    (기존 `±2`세 윈도우 합산 로직 제거). 시그니처에서 `predicted_age` 인자 제거,
    반환 타입은 `Optional[float]`(invalid → None).
  - `_show_success_result()`의 나이 확신도 표시를 새 helper 사용 + None일 때 `-` 표시로 변경.
  - `_gender_label(gender)` staticmethod 추가(`1 → 여성`, `0 → 남성`)하고 성공 표시 경로에서 사용.
  - `import math` 추가.
- `tests/test_main_window.py`
  - 기존 `±2`세 window 기대 테스트 제거, 새 공식 기준 테스트로 재작성
    (stddev↔confidence endpoint/clamp, 분포↔stddev, uniform low-confidence, invalid input,
    GUI 표시 경로, 성별 라벨 contract). preview crop 테스트는 유지.
- `tests/test_result_processor.py`
  - 성별 집계 경계 테스트 보강(`>=0.5→1`, `<0.5→0`, `==0.5→1`, age/gender_confidence
    평균 유지, 30개 미만이면 성별과 무관하게 실패).

수정하지 않은 파일(확인만 함): `src/face_age_gender_predictor/processing/result_processor.py`
(성별 집계 기준이 이미 요구사항과 일치). `AI-Agents/PR.md`, `AI-Agents/REVIEW.md`는 건드리지 않음.

## 변경 이유

- 기존 `±2`세 probability mass 방식은 "나이 확신도"를 분포의 국소 확률 질량으로만
  표현해, test data로 검증된 표준편차 범위(`1.57~8.23`)와 연결되지 않았다. TASK는 분포가
  얼마나 퍼져 있는지를 weighted stddev로 계산해 calibrated confidence로 표시하도록 요구한다.
- 성별 집계는 downstream label contract(`1=여성`, `0=남성`)와 일관성 확인 및 경계값
  테스트 보강이 목적이며, 구현은 이미 일치하므로 테스트만 추가했다.

## 표준편차 공식과 confidence mapping

입력: 26-bin 나이 분포 `age_probs` (ages 15..40 inclusive).

```text
# 1) 정규화 (probability든 unnormalized positive weight든 합>0이면 normalize)
weights = age_probs (음수/NaN/Inf/숫자아님/길이!=26/합<=0 이면 invalid)
norm[i] = weights[i] / sum(weights)

# 2) weighted mean & standard deviation
ages[i] = 15 + i            # i = 0..25
mean    = sum(norm[i] * ages[i])
stddev  = sqrt(sum(norm[i] * (ages[i] - mean)^2))

# 3) inverse linear mapping (낮은 stddev = 높은 confidence)
STDDEV_BEST=1.57, STDDEV_WORST=8.23, CONF_BEST=99.0, CONF_WORST=1.0
ratio      = (stddev - STDDEV_BEST) / (STDDEV_WORST - STDDEV_BEST)
confidence = CONF_BEST - ratio * (CONF_BEST - CONF_WORST)
confidence = clamp(confidence, 1.0, 99.0)
```

- `stddev <= 1.57 → 99%`, `stddev >= 8.23 → 1%`로 clamp.
- invalid 분포 → `None` 반환 → GUI는 `-` 표시(절대 99%로 fallback하지 않음).
- 표시 포맷은 기존 UI와 일관되게 `f"{conf:.1f}%"` 사용(현재 gender confidence 표시도 `.1f`).
  (TASK 예시는 2자리지만, ACCEPTANCE "기존 UI와 일관" + "gender confidence 표시 동일" 기준에
  맞춰 현재 코드의 `.1f`를 유지함. 자릿수 정책은 QA 확인 포인트로 남김.)

## result_processor 성별 최종 집계 기준 확인 결과

`process_predictions()`는 이미 다음과 같이 동작하며 TASK/ACCEPTANCE와 일치한다(코드 변경 없음).

- 유효 prediction만 필터링(`_is_valid_prediction`) 후 집계.
- `avg_gender = mean(valid[i]["gender"])`.
- `final_gender = 1 if avg_gender >= 0.5 else 0` → `>=0.5 → 1(여성)`, `<0.5 → 0(남성)`,
  `==0.5 → 1`.
- age 평균, gender_confidence 평균 집계 유지.
- `valid_count < 30`이면 성별 평균과 무관하게 실패 result 반환.
- 로그도 `여성(1)` / `남성(0)`으로 일치.
- GUI 표시(`_gender_label`, `_show_success_result`)도 `1 → 여성`, `0 → 남성`.

## 요구사항별 구현 결과

| 요구사항 | 결과 |
| --- | --- |
| ±2세 probability mass 방식 제거 | 완료. `_compute_age_confidence` 새 공식으로 교체 |
| 26-bin(15..40) weighted stddev 기반 confidence | 완료. `age_distribution_stddev` |
| stddev 1.57 → 99%, 8.23 → 1%, [1,99] clamp | 완료. `age_confidence_from_stddev` |
| unnormalized positive weight normalize | 완료. 합>0이면 normalize |
| invalid 분포는 high confidence 금지 | 완료. None → `-` 표시 |
| gender confidence 계산/표시 미변경 | 완료. 해당 코드 미수정 |
| age histogram 시각화 유지 | 완료. 히스토그램 로직 미변경 |
| 성별 집계 `>=0.5→1`, `<0.5→0`, `==0.5→1` | 완료(기존 일치) + 경계 테스트 보강 |
| age 평균/gender_confidence 평균/30 미만 실패 유지 | 완료(미변경) + 테스트로 확인 |
| GUI `1→여성`, `0→남성` contract | 완료. `_gender_label` + 테스트 |
| result dict contract 미변경 | 완료. breaking change 없음 |

## Test Results

```text
명령: .\.venv\Scripts\python.exe -m pytest -q --basetemp=".pytest_tmp"
결과: 70 passed in 0.22s

명령(대상 파일만): .\.venv\Scripts\python.exe -m pytest tests/test_main_window.py tests/test_result_processor.py -q
결과: 41 passed in 0.16s
```

주의: 기본 임시 디렉터리(`C:\Users\Public\...\CreatorTemp`)에 대한 쓰기 권한이 없는
환경에서는 `tests/test_cnnmodel.py`의 `tmp_path` 픽스처가 setup 단계에서
`PermissionError [WinError 5]`로 에러난다. 이는 이번 변경과 무관한 환경 권한 문제이며,
`--basetemp=".pytest_tmp"`처럼 쓰기 가능한 경로를 지정하면 70개 전부 통과한다.

새로 추가/갱신한 테스트 핵심:
- `age_confidence_from_stddev`: 1.57→99, 8.23→1, midpoint→50, lower/upper clamp.
- `age_distribution_stddev`: delta→0, uniform→7.5, unnormalized normalize, two-point→target.
- 분포 endpoint: 1.57 분포→≈99%, 8.23 분포→≈1%, uniform→<20% (low).
- invalid(None/[]/len!=26/합0/음수/비수치/NaN/Inf/str)→None (high confidence 아님).
- GUI: `AgeEstimatorWindow._compute_age_confidence` 위임 확인, `_show_success_result`가
  새 confidence 표시(`99.0%`)와 invalid 시 `-` 표시, 성별 라벨(`여성`/`남성`) 확인.
- result_processor: 성별 `>=0.5→1`, `<0.5→0`, `==0.5→1`, age/gender_confidence 평균 유지,
  30 미만 실패 유지.

## 남은 위험 요소 / Not Verified

- **모델 gender label 자체(1=여성, 0=남성)는 코드상 보장되지 않음 (Not Verified)**:
  `src/face_age_gender_predictor/inference/CNNmodel.py`는 모델의 `predicted_gender`
  원시 출력을 그대로 prediction dict의 `gender` float으로 전달한다(`CNNmodel.py:411-420`).
  앱 내부 contract(`1→여성`, `0→남성`)는 문서/구현/테스트에서 일관되지만, 실제 학습 모델의
  output label이 이 의미와 같은지는 코드만으로 확인 불가. 모델 담당 확인 또는 실측 필요.
- **표시 자릿수 정책**: age confidence를 `.1f`로 표시(현재 gender confidence와 동일). TASK
  예시는 2자리(`99.00%`)였으나 ACCEPTANCE의 "기존 UI 일관" 기준을 우선했다. 2자리를 원하면
  `_show_success_result`의 포맷 한 줄만 바꾸면 된다(QA 결정 포인트).
- **실제 웹캠 end-to-end QA는 범위 밖**: 본 작업은 helper/표시/테스트 단위까지만 검증했다.
  실제 카메라 흐름에서의 표시는 사용자/QA 수동 확인 영역.

## Codex QA가 집중해서 봐야 할 부분

1. 매핑 정확성: `age_confidence_from_stddev`의 1.57→99 / 8.23→1 / clamp 경계, 그리고
   분포→stddev(`age_distribution_stddev`)의 normalize/weighted 계산.
2. invalid 방어: TASK 핵심 조건인 "invalid 분포가 high confidence로 fallback하지 않음"이
   모든 invalid 케이스에서 지켜지는지(None→`-`).
3. 표시 경로 연결: `_show_success_result`가 새 helper를 쓰고, gender confidence/histogram은
   변경되지 않았는지.
4. 성별 집계: `result_processor`가 코드 변경 없이 요구 기준과 일치하는지, 경계값(0.5) 처리.
5. 모델 gender label contract Not Verified 항목(위)에 대한 후속 판단.

---

## QA Fix Round

Codex QA `REVIEW.md` (Verdict: NEEDS_FIX)의 지적을 반영했다.

### 수정한 지적과 변경 파일

- **Finding 2 (NEEDS_FIX) — 성공 결과 표시 경로가 invalid `age_probs`를 안전하게 처리하지 못함 (수정 완료)**
  - 문제: `_show_success_result()`가 confidence는 `age_confidence_percent() → None`으로
    invalid를 걸러 `-`를 표시하면서도, 바로 뒤에서 같은 `age_probs`를
    `int(round(p * 1000))`로 히스토그램 변환했다. NaN/Inf/비숫자 값이 있으면
    `ValueError: cannot convert float NaN to integer`로 예외가 발생했다.
  - 수정(`src/face_age_gender_predictor/app/main_window.py`):
    `_show_success_result()`에서 confidence 유효성(`age_confidence is None`) 판단을
    히스토그램에도 동일하게 적용했다. 유효하면 confidence 표시 + 히스토그램 변환,
    유효하지 않으면 `-` 표시 + 빈 히스토그램(`clear_values()`)으로 처리한다.
    (TASK invalid input policy: NaN/Inf/비숫자/wrong length는 unavailable 상태로 표시,
    히스토그램 시각화 자체는 유지)
  - 검증(REVIEW와 동일한 smoke): `[float('nan')] * 26` 입력 시 예외 없이
    `nan_age_probs_display_ok=True`, `age_conf_text='-'`. (이전: `False` + `ValueError`)
  - 테스트 추가(`tests/test_main_window.py`):
    `test_success_display_invalid_age_probs_no_exception_and_empty_histogram`을
    parametrize로 추가 — NaN / Inf / 비숫자 / 음수 / 길이≠26 / 합 0 케이스 모두
    예외 없이 `-` + 빈 히스토그램이 되는지 검증한다.

### Claude 범위 밖이라 수정하지 않은 지적 (BLOCKED / 위임)

- **Finding 1 & 4 (NEEDS_FIX) — `AI-Agents/PR.md` 변경 / trailing whitespace**:
  `CLAUDE.md`는 "Claude는 `AI-Agents/PR.md`를 어떤 경우에도 수정하지 않는다"고 명시하며,
  `TASK.md`의 "수정하지 말 것"에도 PR.md가 포함된다. 또한 이번 task 시작 시 하네스가
  "PR.md는 사용자/린터가 의도적으로 수정했으며, 사용자가 요청하지 않는 한 되돌리지 말라"고
  안내했다. REVIEW Follow-up 역시 "PR 문서는 이후 release/PR 준비 단계에서 사용자 또는
  Codex Release 담당이 다시 작성/정리한다"고 명시한다.
  → 따라서 Claude는 PR.md를 수정/되돌리지 않았다. **BLOCKED: PR.md의 변경 제외와
  trailing whitespace 정리는 사용자/Codex Release 담당이 처리해야 한다.**
  (참고: 이번 QA Fix에서 Claude가 실제 편집한 파일은 PR.md를 포함하지 않는다.)

- **Finding 3 (NEEDS_FIX) — 범위 밖 파일 변경(`.gitignore`, `CLAUDE.md`, `TASK.md`,
  `ACCEPTANCE.md`, `PR.md`)이 diff에 존재**:
  이 파일들은 이번 age confidence 작업에서 Claude가 편집한 파일이 아니며, 작업 브랜치가
  새 task용으로 준비될 때 이미 수정되어 있던 상태(branch 준비분)다. 이번 QA Fix에서
  Claude가 편집한 파일은 `main_window.py`, `tests/test_main_window.py`,
  `AI-Agents/IMPLEMENTATION.md` 뿐이다. 어떤 변경을 커밋 diff에 포함/제외할지는
  커밋 시점의 scope 결정 사항이며 Claude가 커밋을 수행하지 않는다.
  → **BLOCKED(위임): 커밋 전 `.gitignore`/`CLAUDE.md` 등 branch 준비분을 이번 구현
  diff에 포함할지 여부는 사용자/Codex Release가 분리 판단한다.** Claude가 만들지 않은
  변경을 임의로 되돌리면 task 준비 상태(예: 이번 TASK.md/ACCEPTANCE.md)가 깨질 수 있어
  되돌리지 않았다.

### 다시 실행한 테스트

```text
명령: .\.venv\Scripts\python.exe -m pytest tests/test_main_window.py tests/test_result_processor.py -q --basetemp=".pytest_tmp"
결과: 47 passed (이전 41 → invalid age_probs GUI 표시 테스트 6 케이스 추가)

명령: .\.venv\Scripts\python.exe -m pytest -q --basetemp=".pytest_tmp"
결과: 76 passed

명령(REVIEW와 동일 smoke): NaN age_probs로 _show_success_result 호출
결과: nan_age_probs_display_ok=True, age_conf_text='-' (예외 없음)

확인: git diff --check (내가 편집한 main_window.py / test_main_window.py) → whitespace 오류 없음
확인: 편집 파일 UTF-8 유지
```

### 아직 남은 BLOCKED 항목

- **`AI-Agents/PR.md` 변경 및 trailing whitespace (Finding 1, 4)**: Claude 수정 금지 파일.
  사용자/Codex Release가 PR.md 변경 제외 또는 정리 필요. `git diff --check`는 PR.md가
  정리되기 전까지 실패 상태로 남는다.
- **커밋 scope 정리 (Finding 3)**: branch 준비분(`.gitignore`, `CLAUDE.md` 등)을 이번
  구현 커밋에 포함할지 사용자/Codex Release가 분리 판단.
- (이전 라운드에서 이어짐) 모델 gender label(`1=여성/0=남성`) 실측 Not Verified,
  실제 웹캠 end-to-end 수동 QA는 범위 밖.
