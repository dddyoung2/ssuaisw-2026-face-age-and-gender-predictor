# IMPLEMENTATION

## Status

완료. Claude Code 구현이 끝난 뒤, 토큰 아웃으로 중단된 구현 보고서를 Codex QA가 현재 파일과 테스트 결과 기준으로 마무리했다.

## Summary

- 현재 GUI(`AgeEstimatorWindow`)의 기능 흐름은 유지하면서, 화면 디자인을 밝은 블루/화이트 light theme 방향으로 재정렬했다.
- 첨부 구버전 GUI의 디자인 방향을 참고하되, 구버전의 로직은 가져오지 않았다. 특히 예측 나이 `±2`세 확률 질량 방식의 age confidence는 사용하지 않고, 현행 표준편차 기반 age confidence를 유지했다.
- 결과 패널은 2-column grid 형태로 정리했고, 카드/버튼/progress/histogram/preview 영역의 색상, 여백, border, 대비를 light theme에 맞게 조정했다.
- GitHub CI에서 실패했던 `average_gender == 0.5` 경계 케이스는 `result_processor` 평균 계산을 `math.fsum` 기반으로 바꿔 numeric stability를 보강했다. 성별 threshold 정책(`average_gender >= 0.5 -> 1`)은 변경하지 않았다.
- 카메라/worker/thread/signal-slot 흐름, 모델 inference 경로, result dict contract, 나이 확신도 공식, invalid `age_probs` 방어, 성별 표시 contract는 유지했다.

## Changed Files

- `src/face_age_gender_predictor/app/main_window.py`
  - module docstring을 현행 작업 범위에 맞게 갱신했다.
  - 전체 stylesheet를 navy/dark 중심에서 light blue/white 중심으로 교체했다.
  - root/window 배경을 `#eaf3ff` 계열로 변경했다.
  - `videoCard`, `sidePanel`, `previewCard`, `metricCard`, helper/progress 영역을 흰색 또는 옅은 블루 카드와 연한 border로 정리했다.
  - 측정 버튼을 파란 primary 버튼(`#2f63f6`)으로 바꾸고, 시작/종료 버튼은 light theme의 secondary 스타일로 정리했다.
  - `AgeHistogramWidget`의 배경, border, 막대 색, 라벨 색, 높이를 light theme에 맞게 조정했다.
  - 결과 preview 얼굴 크기를 `150x150`에서 `130x130`으로 줄이고, 결과 정보 영역을 `QVBoxLayout`에서 2-column `QGridLayout`으로 재배치했다.
  - 상태 accent 색, face box overlay, preview/result text color를 light theme에서 읽히도록 조정했다.
  - `enter_state()`가 custom hint가 없을 때 상태별 기본 hint를 helper 영역에 표시하도록 정리했다.
  - 나이 확신도 계산, invalid `age_probs` 처리, `_gender_label`, histogram 값 생성 조건은 현행 로직을 유지했다.

- `src/face_age_gender_predictor/processing/result_processor.py`
  - `import math`를 추가했다.
  - `avg_age`, `avg_gender`, `avg_gender_confidence` 계산을 `sum(...)`에서 `math.fsum(...)`으로 변경했다.
  - 이 변경은 부동소수점 누적 오차를 줄이기 위한 numeric stability fix이며, 성별 threshold 정책과 result dict contract는 그대로다.

- `AI-Agents/IMPLEMENTATION.md`
  - Claude가 작성 중 중단한 구현 보고서를 현재 파일 상태와 검증 결과에 맞춰 완성했다.

## Design Changes

- 배경: 앱 전체 배경을 밝은 블루 계열 `#eaf3ff`로 정리했다.
- 카드: 주요 패널과 결과 카드는 `#fbfdff`/`#ffffff` 배경, `#dbe7f5`/`#d7e3f2` border, 12~18px radius를 사용한다.
- 버튼: 측정 버튼은 파란 primary 스타일, 시작/종료 버튼은 흰색 secondary 스타일로 구분했다.
- Progress bar: 흰색 트랙과 파란 chunk로 light theme에 맞췄다.
- 결과 영역: 성별/나이와 각 확신도를 2-column grid로 배치해 더 compact하게 보이도록 했다.
- Preview: 얼굴 preview는 더 작은 고정 크기와 light border를 사용한다.
- Histogram: 흰 배경, 연한 border, 파란 막대, 읽기 쉬운 라벨 색으로 바꿨다.
- Camera overlay: 카메라 영상 자체는 어두운 surface를 유지하되, face box와 banner 색을 light theme과 어울리는 파란/회색 계열로 조정했다.

## Logic Preservation

- 나이 확신도:
  - `age_distribution_stddev()`, `age_confidence_from_stddev()`, `age_confidence_percent()`, `_compute_age_confidence()`의 계산 정책은 유지했다.
  - 26-bin(15~40) weighted stddev, `1.57 -> 99%`, `8.23 -> 1%`, `[1, 99]` clamp가 유지된다.
  - 구버전 첨부 코드의 `predicted_age ±2` probability mass 방식은 되살리지 않았다.

- invalid `age_probs`:
  - invalid 분포는 높은 confidence로 fallback하지 않는다.
  - GUI에서는 `-` 표시와 빈 histogram 처리가 유지된다.

- 성별 표시:
  - `_gender_label()`의 `gender == 1 -> 여성`, `gender == 0 -> 남성` contract가 유지된다.
  - 바뀐 것은 light theme용 표시 색상뿐이다.

- 성별 집계:
  - `average_gender >= 0.5 -> 1`, `< 0.5 -> 0` 정책은 유지했다.
  - `math.fsum` 적용은 정책 변경이 아니라 float 경계값 안정화다.

- 기타:
  - camera/worker/thread/timer/signal-slot 흐름은 변경하지 않았다.
  - 모델 inference 코드와 모델 파일은 변경하지 않았다.
  - result dict key/shape contract는 변경하지 않았다.

## CI Boundary Fix

GitHub Actions에서 다음 테스트가 실패했다.

```text
tests/test_result_processor.py::test_age_and_gender_confidence_averages_preserved_with_gender_change
```

원인은 `gender` 값이 수학적으로 평균 `0.5`가 되는 입력에서 일반 `sum`의 부동소수점 누적 오차가 플랫폼/실행 환경에 따라 `0.5`보다 미세하게 작은 값으로 떨어질 수 있기 때문이다. 이 경우 기존 정책상 `>= 0.5`면 `1`이어야 하는데, 실제 비교가 `< 0.5`로 판정되어 `0`이 될 수 있다.

수정:

```python
avg_gender = math.fsum(p["gender"] for p in valid) / n
```

같은 이유로 `avg_age`, `avg_gender_confidence`도 `math.fsum`을 사용하도록 맞췄다.

검증 기준:

- `[0.1] * 20 + [0.9] * 20` 조합은 최종 `gender == 1`이어야 한다.
- `average_gender == 0.5` 경계 테스트는 계속 유지되어야 한다.
- age 평균, gender_confidence 평균, valid_count < 30 실패 조건은 그대로 유지되어야 한다.

## Requirement Mapping

| Requirement | Result |
| --- | --- |
| GUI 디자인 변경에 한정 | 완료. 주 변경은 `main_window.py` presentation 영역 |
| 구버전 코드는 디자인 참고로만 사용 | 완료. 구버전 age confidence 로직 미사용 |
| 밝은 블루/화이트 계열 visual style | 완료 |
| 카드/패널/결과 영역 light border와 padding | 완료 |
| primary 버튼/progress light theme 정리 | 완료 |
| preview/camera 비율 유지 | 완료. preview 크기만 축소 |
| 결과 텍스트 2-column 정리 | 완료. `QGridLayout` 적용 |
| histogram readable light theme | 완료 |
| 나이 확신도 표준편차 공식 유지 | 완료 |
| invalid `age_probs` 방어 유지 | 완료 |
| 성별 표시 contract 유지 | 완료 |
| `result_processor` threshold 정책 유지 | 완료 |
| `average_gender == 0.5` CI 경계 안정화 | 완료. `math.fsum` 적용 |
| camera/worker/thread 흐름 미변경 | 완료 |
| 모델 inference/모델 파일 미변경 | 완료 |
| PR 문서 작성/갱신 없음 | 구현 보고서 기준 PR 작성 없음 |

## Test Results

```text
명령: .\.venv\Scripts\python.exe -m pytest -q --basetemp "C:\Users\Public\Documents\ESTsoft\CreatorTemp\pytest-implementation-qa"
결과: PASS - 76 passed, 1 warning in 0.26s
비고: pytest cache path 생성 권한 warning 발생

명령: .\.venv\Scripts\python.exe -m pytest tests\test_main_window.py tests\test_result_processor.py -q --basetemp "C:\Users\Public\Documents\ESTsoft\CreatorTemp\pytest-implementation-qa-target"
결과: PASS - 47 passed, 1 warning in 0.18s
비고: pytest cache path 생성 권한 warning 발생

명령: .\.venv\Scripts\python.exe -m pytest tests\test_result_processor.py::test_age_and_gender_confidence_averages_preserved_with_gender_change -q --basetemp "C:\Users\Public\Documents\ESTsoft\CreatorTemp\pytest-implementation-qa-ci"
결과: PASS - 1 passed, 1 warning in 0.01s

명령: .\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\processing\result_processor.py
결과: PASS

명령: git diff --check -- AI-Agents\IMPLEMENTATION.md src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\processing\result_processor.py
결과: PASS
```

추가 offscreen GUI smoke:

```text
성공 result smoke:
- success_gender=여성
- success_age=27세
- success_gconf=90.0%
- success_aconf=99.0%
- hist_nonempty=True
- size_hint_valid=True
- style_light=True

실패 result smoke(QMessageBox.information stub):
- failure_age=실패
- failure_gender=미정
- failure_aconf=-
- hist_empty=True
```

## Not Verified

- 실제 데스크톱/웹캠 환경에서의 수동 GUI QA는 수행하지 못했다.
- 실제 화면에서의 색감, 대비, 텍스트 overflow, 다양한 DPI/해상도에서의 레이아웃은 사용자가 수동 확인해야 한다.
- 실제 카메라 preview와 live face box 렌더링은 offscreen smoke로는 육안 검증하지 못했다.
- 모델의 실제 학습 label이 `gender == 1 -> 여성`, `gender == 0 -> 남성`인지 코드상 완전히 보장되지는 않는다. 앱 내부 downstream contract만 유지했다.

## Follow-up

- 사용자는 commit 후 pull 받아 실제 GUI에서 화면 겹침, 버튼 상태, 결과 표시, histogram 가독성, 반복 측정 흐름을 수동 QA한다.
- release/PR 담당 단계에서 `AI-Agents/PR.md`를 별도로 작성한다.
