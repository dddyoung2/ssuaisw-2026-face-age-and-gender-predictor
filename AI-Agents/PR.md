# PR

## PR 제목 제안

feat(gui): 결과 화면 light theme 디자인 적용

## 변경 요약

- GUI 결과/측정 화면을 밝은 블루/화이트 계열 light theme으로 정리했습니다.
- 카드, 버튼, progress bar, histogram, preview/result 영역의 색상, 여백, border, typography를 조정했습니다.
- 결과 preview 정보를 2-column grid 형태로 정리하고 얼굴 preview 크기를 compact하게 조정했습니다.
- 첨부된 구버전 GUI 코드는 디자인 참고로만 사용했고, 구버전 나이 확신도 로직은 가져오지 않았습니다.
- 현재 나이 확신도 표준편차 기반 공식, invalid `age_probs` 처리, 성별 표시 contract는 유지했습니다.
- GitHub CI에서 실패했던 `average_gender == 0.5` 경계 케이스를 안정화하기 위해 `result_processor` 평균 계산을 `math.fsum` 기반으로 변경했습니다.

## 주요 변경 파일

- `src/face_age_gender_predictor/app/main_window.py`
- `src/face_age_gender_predictor/processing/result_processor.py`
- `AI-Agents/TASK.md`
- `AI-Agents/ACCEPTANCE.md`
- `AI-Agents/IMPLEMENTATION.md`
- `AI-Agents/REVIEW.md`
- `AI-Agents/PR.md`

## 테스트 결과

```text
PASS:
- C:\Users\jads7\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\processing\result_processor.py
- Codex 번들 Python + PYTHONPATH=src result_processor average_gender == 0.5 smoke
  - success=True, gender=1, valid_count=40
- git diff --check

BLOCKED:
- .\.venv\Scripts\python.exe -m pytest -q --basetemp ".pytest_tmp_release"
- .\.venv\Scripts\python.exe -m py_compile ...
  - 로컬 .venv가 삭제/이동된 Python 경로(C:\Users\jads7\AppData\Local\Programs\Python\Python311\python.exe)를 참조해 실행 실패
```

## 보안/개인정보 확인

- [x] `.env`, `.env.*`, secret, token, private key가 변경 목록에 없습니다.
- [x] 개인 이미지 또는 개인정보 파일이 변경 목록에 없습니다.
- [x] `models/*.pt`, `models/*.pth`, `models/*.onnx` 파일이 변경 목록에 없습니다.
- [x] 빌드 산출물, 캐시 산출물, 대용량 모델 파일이 변경 목록에 없습니다.
- [x] 현재 브랜치는 `codex/age-confidence-stddev-formula-task`이며 `main` 직접 push가 아닙니다.

## BLOCKED 또는 후속 작업

- PR 진행 blocker는 없습니다. `AI-Agents/REVIEW.md` Verdict는 `PASS`입니다.
- 전체 pytest는 로컬 `.venv` Python 경로 문제로 실행하지 못했습니다. 가상환경 복구 후 재실행이 필요합니다.
- 실제 웹캠 GUI end-to-end 수동 QA는 수행하지 않았습니다.
- 다양한 DPI/해상도에서의 레이아웃, 텍스트 overflow, histogram 가독성은 수동 확인이 필요합니다.
- 모델의 실제 학습 label이 `gender == 1 -> 여성`, `gender == 0 -> 남성`과 일치하는지는 Not Verified입니다.

## Suggested PR Body

```markdown
## 변경 요약
- GUI 결과/측정 화면을 밝은 블루/화이트 계열 light theme으로 정리했습니다.
- 카드, 버튼, progress bar, histogram, preview/result 영역의 색상, 여백, border, typography를 조정했습니다.
- 결과 preview 정보를 2-column grid 형태로 정리하고 얼굴 preview 크기를 compact하게 조정했습니다.
- 첨부 구버전 GUI 코드는 디자인 참고로만 사용했고, 구버전 나이 확신도 로직은 가져오지 않았습니다.
- 현재 나이 확신도 표준편차 기반 공식, invalid `age_probs` 처리, 성별 표시 contract는 유지했습니다.
- GitHub CI의 `average_gender == 0.5` 경계 실패를 막기 위해 `result_processor` 평균 계산을 `math.fsum` 기반으로 안정화했습니다.

## 테스트
- [x] `C:\Users\jads7\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\processing\result_processor.py`
- [x] Codex 번들 Python + `PYTHONPATH=src` result_processor `average_gender == 0.5` smoke
  - `success=True`, `gender=1`, `valid_count=40`
- [x] `git diff --check`
- [ ] `.\.venv\Scripts\python.exe -m pytest -q --basetemp ".pytest_tmp_release"`
  - BLOCKED: 로컬 `.venv`가 삭제/이동된 Python 경로를 참조해 실행 실패

## 보안/개인정보 확인
- `.env`, secret, 개인 이미지, 모델 파일, 빌드/캐시 산출물은 변경 목록에 없습니다.
- 현재 브랜치는 `codex/age-confidence-stddev-formula-task`이며 `main` 직접 push가 아닙니다.

## Not Verified / Follow-up
- 실제 웹캠 GUI end-to-end 수동 QA는 수행하지 않았습니다.
- 다양한 DPI/해상도에서의 레이아웃, 텍스트 overflow, histogram 가독성은 수동 확인이 필요합니다.
- 모델의 실제 학습 label이 `1=여성`, `0=남성`인지 코드는 보장하지 않습니다. 앱 내부 downstream contract만 확인했습니다.
- 로컬 `.venv` 복구 후 전체 pytest 재실행이 필요합니다.
```
