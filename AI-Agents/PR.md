# PR

## PR 제목 제안

fix(app): 표준편차 기반 나이 확신도 적용

## 변경 요약

- GUI의 나이 확신도 표시를 기존 예측 나이 `±2`세 확률 질량 방식에서 26-bin 나이 분포의 weighted standard deviation 기반 보정 공식으로 교체했습니다.
- 표준편차 `1.57 -> 99%`, `8.23 -> 1%`의 inverse linear mapping을 적용하고, valid distribution은 `[1%, 99%]` 범위로 clamp합니다.
- invalid `age_probs` 입력(`None`, wrong length, NaN/Inf, 비숫자, 음수, 합 0 등)은 높은 confidence로 fallback하지 않고 `-`와 빈 히스토그램으로 안전하게 표시합니다.
- `result_processor`의 성별 최종 집계 기준이 유효 prediction의 `gender` 평균값 기준(`average_gender >= 0.5 -> 1`, `< 0.5 -> 0`)과 일치함을 확인하고 테스트를 보강했습니다.
- 앱 내부 성별 label contract는 `gender == 1 -> 여성`, `gender == 0 -> 남성`으로 확인했습니다.
- 모델의 실제 학습 label이 `1=여성`, `0=남성`인지 여부는 코드만으로 보장되지 않아 Not Verified / Follow-up으로 남겼습니다.
- `.gitignore`의 `logs/` 추가와 `CLAUDE.md`의 PR 문서 수정 금지 명시는 사용자 의도 변경으로 확인된 branch 준비 변경입니다.

## 주요 변경 파일

- `src/face_age_gender_predictor/app/main_window.py`
- `tests/test_main_window.py`
- `tests/test_result_processor.py`
- `AI-Agents/TASK.md`
- `AI-Agents/ACCEPTANCE.md`
- `AI-Agents/IMPLEMENTATION.md`
- `AI-Agents/REVIEW.md`
- `AI-Agents/PR.md`
- `.gitignore`
- `CLAUDE.md`

## 테스트 결과

```text
명령: .\.venv\Scripts\python.exe -m pytest -q --basetemp ".pytest_tmp_release"
결과: PASS - 76 passed, 1 warning in 0.24s

경고:
.pytest_cache 경로 생성 권한 없음(PytestCacheWarning, WinError 5)

명령: .\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\processing\result_processor.py
결과: PASS
```

## 보안/개인정보 확인

- [x] `.env`, `.env.*`, secret, token, private key가 변경 목록에 없습니다.
- [x] 개인 이미지 또는 개인정보 파일이 변경 목록에 없습니다.
- [x] `models/*.pt`, `models/*.pth`, `models/*.onnx` 파일이 변경 목록에 없습니다.
- [x] 빌드 산출물, 캐시 산출물, 대용량 모델 파일이 변경 목록에 없습니다.
- [x] 현재 브랜치는 `codex/age-confidence-stddev-formula-task`이며 `main` 직접 push가 아닙니다.

## BLOCKED 또는 후속 작업

- PR 진행 blocker는 없습니다. `AI-Agents/REVIEW.md` Verdict는 `PASS`입니다.
- 실제 웹캠 GUI end-to-end 수동 QA는 수행하지 않았습니다.
- 모델의 실제 학습 label이 `gender == 1 -> 여성`, `gender == 0 -> 남성`과 일치하는지는 Not Verified입니다.
- age confidence 표시 자릿수는 기존 UI와 맞춰 `.1f%`를 유지했습니다. `99.00%` 같은 2자리 표시를 원하면 후속으로 포맷 정책을 결정하면 됩니다.
- GitHub push와 PR 생성은 사용자 승인 후 진행합니다. merge는 하지 않습니다.

## Suggested PR Body

```markdown
## 변경 요약
- GUI 나이 확신도를 26-bin 나이 분포의 weighted standard deviation 기반 보정 공식으로 변경했습니다.
- 표준편차 `1.57 -> 99%`, `8.23 -> 1%` mapping과 `[1%, 99%]` clamp를 적용했습니다.
- invalid `age_probs`가 높은 confidence로 fallback하지 않도록 `-`와 빈 히스토그램으로 안전 처리했습니다.
- `result_processor`의 성별 최종 집계 기준이 `average_gender >= 0.5 -> 1(여성)`, `< 0.5 -> 0(남성)`과 일치함을 확인하고 테스트를 보강했습니다.
- 성별 confidence 평균, age 평균, valid_count 30개 미만 실패 조건은 유지했습니다.

## 테스트
- [x] `.\.venv\Scripts\python.exe -m pytest -q --basetemp ".pytest_tmp_release"`
  - `76 passed, 1 warning`
- [x] `.\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\processing\result_processor.py`

## 보안/개인정보 확인
- `.env`, secret, 개인 이미지, 모델 파일, 빌드/캐시 산출물은 변경 목록에 없습니다.
- 현재 브랜치는 `codex/age-confidence-stddev-formula-task`이며 `main` 직접 push가 아닙니다.

## Not Verified / Follow-up
- 실제 웹캠 GUI end-to-end 수동 QA는 수행하지 않았습니다.
- 모델의 실제 학습 label이 `1=여성`, `0=남성`인지 코드는 보장하지 않습니다. 앱 내부 downstream contract만 확인했습니다.
- age confidence 표시 자릿수는 기존 UI와 맞춰 `.1f%`를 유지했습니다.
```
