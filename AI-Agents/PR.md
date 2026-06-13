# PR

## PR 제목 제안

feat(app): 실제 모델 추론 연결과 반복 측정 흐름 안정화

## 변경 요약

- 한 번 측정이 끝난 뒤 앱을 재시작하지 않아도 다시 얼굴을 인식하고, 얼굴 준비 상태가 되면 측정 버튼이 다시 활성화되도록 재측정 흐름을 보강했습니다.
- 재측정 버튼이 다시 활성화되어도 이전 결과 화면은 유지하고, 사용자가 새 측정을 시작하는 순간 이전 결과/진행 상태를 초기화하도록 GUI 상태 흐름을 정리했습니다.
- `InferenceWorker`의 임시 랜덤 prediction 경로를 제거하고 `CNNmodel.predict_frames()`를 호출하는 실제 추론 경로로 연결했습니다.
- `CNNmodel.py`를 import-safe한 앱용 모듈로 정리해, import 시점에 모델 로드/샘플 이미지 추론/plot 표시가 자동 실행되지 않도록 했습니다.
- 기본 모델 경로를 repository-root 기준 `models/Best_Age_Estimate_model_traced.pt`로 해석하고, 모델 파일이 없을 때 명확한 오류를 전달하도록 했습니다.
- TorchScript 모델 로드와 전처리/추론은 `InferenceWorker`/`InferenceThread` 경로에 남기고, GUI MainThread는 상태와 화면 갱신만 담당하도록 QThread 경계를 확인했습니다.
- 결과 얼굴 preview가 재측정 중 live detection frame에 덮여 비거나 stale 상태가 되는 문제를 방지하기 위해, 측정 시점의 captured frame/face box snapshot을 결과 표시용으로 사용하도록 보강했습니다.
- 나이 confidence 표시는 단일 최대 class 확률 대신 예측 나이 ±2세 구간의 확률 질량을 합산하고 0~100%로 clamp하도록 조정했습니다.
- 모델 연결, QThread/컨트롤러 상태 전이, 재측정 preview, 나이 confidence 계산에 대한 자동 테스트를 추가/보강했습니다.

## 주요 변경 파일

- `src/face_age_gender_predictor/inference/CNNmodel.py`
  - import side effect 제거, lazy model load/cache, `predict_frames()` 앱용 API 추가, 기본 모델 경로 해석 및 오류 처리.
- `src/face_age_gender_predictor/app/workers.py`
  - `InferenceWorker`가 랜덤 prediction 대신 `CNNmodel.predict_frames()`를 호출하도록 변경.
- `src/face_age_gender_predictor/app/main_app.py`
  - QThread 연결 경로와 반복 측정 상태 회복 흐름 보강.
- `src/face_age_gender_predictor/app/main_window.py`
  - 재측정 UX, 결과 preview snapshot, 나이 confidence 계산 보강.
- `src/face_age_gender_predictor/camera/camera_detector.py`
  - 감지 재개 및 촬영 직전 얼굴 검증 흐름 보강.
- `tests/test_cnnmodel.py`
  - 모델 API, import side effect, 기본 모델 경로, missing model, preprocessing/inference 계약 테스트.
- `tests/test_controller.py`
  - 성공/실패 후 IDLE 복귀, 재감지 후 측정 버튼 재활성화, 2차 측정 시작 상태 전이 테스트.
- `tests/test_window_preview.py`
  - 반복 측정 후 결과 preview가 비지 않는지 검증.
- `tests/test_main_window.py`
  - 나이 confidence ±2세 구간 합산/clamp 테스트.
- `tests/conftest.py`
  - offscreen `QApplication` fixture 추가.
- `tests/test_camera_detector.py`, `tests/test_workers.py`
  - camera resume/validation, worker delegation/error routing 테스트 보강.
- `README.md`, `docs/components.md`, `docs/development.md`
  - 현재 실행/모델 연결 흐름에 맞춘 설명 보정.
- `pyproject.toml`
  - 테스트/프로젝트 설정 보강.
- `AI-Agents/TASK.md`, `AI-Agents/ACCEPTANCE.md`, `AI-Agents/IMPLEMENTATION.md`, `AI-Agents/REVIEW.md`
  - 작업 정의, 수용 기준, 구현 보고, QA 결과 갱신.

참고:

- `scripts/test_run.py`는 `git status`에 modified로 표시되지만 `git diff -- scripts/test_run.py`에는 내용 diff가 없습니다. line-ending/status noise로 보이며, stage 전 최종 확인이 필요합니다.
- 신규 테스트 파일은 현재 untracked 상태이므로 커밋 시 의도적으로 stage해야 합니다:
  - `tests/conftest.py`
  - `tests/test_cnnmodel.py`
  - `tests/test_controller.py`
  - `tests/test_main_window.py`
  - `tests/test_window_preview.py`

## 테스트 결과

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS - 41 passed in 0.41s

명령: .\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\app\main_app.py src\face_age_gender_predictor\app\workers.py src\face_age_gender_predictor\camera\camera_detector.py src\face_age_gender_predictor\inference\CNNmodel.py
결과: PASS

명령: git diff --check
결과: PASS
비고: LF -> CRLF line-ending warning만 출력됨.

명령: .\.venv\Scripts\python.exe -m pip check
결과: PASS - No broken requirements found.

명령: .\.venv\Scripts\python.exe -c "import mediapipe as mp, cv2, numpy as np; ..."
결과: PASS - mediapipe 0.10.21, mp.solutions=True, cv2 4.11.0, numpy 1.26.4

명령: .\.venv\Scripts\python.exe -c "import face_age_gender_predictor.app.main_app as app; ..."
결과: PASS - main_app import ok IDLE

명령: .\.venv\Scripts\python.exe -c "from face_age_gender_predictor.inference import CNNmodel; CNNmodel.load_model(); CNNmodel._run_model(...); ..."
결과: PASS - device cpu, outputs 4, shapes [(1,), (1,), (1, 26), (1,)], age_probs_sum 1.0
```

## 보안/개인정보 확인

- `git ls-files .env .env.local *.pt *.pth *.onnx models` 결과 tracked 금지 파일 없음.
- 로컬 `models/Best_Age_Estimate_model_traced.pt`는 약 601 MB로 존재하지만 `git status --short --ignored models` 기준 `!! models/`로 ignored 상태이며 tracked/staged 대상이 아닙니다.
- `.env`, secret, 개인 이미지, 모델 artifact, 빌드 산출물은 현재 변경 목록에 포함되지 않았습니다.
- 현재 브랜치는 `feature/gui-qthread-integration`이며 `main` 직접 push가 아닙니다.
- `docs/GIT-WORKFLOW.md`는 저장소에 없어서 `AGENTS.md`의 Git/Release 규칙을 적용했습니다.

## BLOCKED 또는 후속 작업

- `REVIEW.md` Verdict는 `PASS`입니다.
- 실제 웹캠 GUI end-to-end는 아직 Not Verified입니다. 사용자 환경에서 아래 수동 QA가 필요합니다:
  - 첫 측정 성공
  - 결과 얼굴 사진 표시
  - 자동 재감지
  - 측정 버튼 재활성화
  - 두 번째 측정 성공
  - 앱 종료 시 카메라 리소스 해제
- 실제 PyQt 창에서 모델 파일 누락 오류가 어떻게 보이는지는 모델 파일이 현재 로컬에 존재해 직접 확인하지 못했습니다.
- `tests/test_window_preview.py`는 결과 preview가 비지 않는 회귀는 잡지만, 첫 번째 측정 이미지가 두 번째 측정에 재사용되는 stale-image 회귀까지 강하게 검증하지는 않습니다. 후속으로 second measurement frame을 시각적으로 다르게 만들어 assert를 강화할 수 있습니다.
- commit/push/PR 생성은 사용자 승인 후 진행해야 합니다. merge는 하지 않습니다.

## Suggested PR Body

```markdown
## 변경 요약

- 반복 측정 흐름을 보강해, 한 번 측정이 완료된 뒤에도 앱 재시작 없이 얼굴 재감지 후 측정 버튼이 다시 활성화되도록 했습니다.
- 재측정 버튼이 다시 활성화되어도 이전 결과는 유지하고, 새 측정 시작 시점에 이전 결과/진행 상태를 초기화하도록 정리했습니다.
- `InferenceWorker`의 랜덤 임시 prediction 경로를 제거하고 `CNNmodel.predict_frames()` 기반 실제 TorchScript 추론 경로로 연결했습니다.
- `CNNmodel.py` import 시 모델 로드/샘플 추론/plot 표시가 자동 실행되지 않도록 앱용 API로 정리했습니다.
- 결과 얼굴 preview snapshot, 나이 confidence 계산, QThread 기반 추론 경로를 보강했습니다.
- 모델 연결, 반복 측정, QThread/worker 경계, GUI preview, 나이 confidence 관련 테스트를 추가/갱신했습니다.

## 테스트

- [x] `.\.venv\Scripts\python.exe -m pytest -q`
  - `41 passed in 0.41s`
- [x] `.\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\app\main_app.py src\face_age_gender_predictor\app\workers.py src\face_age_gender_predictor\camera\camera_detector.py src\face_age_gender_predictor\inference\CNNmodel.py`
- [x] `git diff --check`
  - PASS, line-ending warning만 출력
- [x] `.\.venv\Scripts\python.exe -m pip check`
  - `No broken requirements found.`
- [x] mediapipe/cv2/numpy import smoke
- [x] `main_app` import smoke
- [x] real model smoke
  - CPU load/forward 성공, output shapes `[(1,), (1,), (1, 26), (1,)]`, `age_probs_sum=1.0`

## 보안/개인정보 확인

- tracked `.env`, secret, 개인 이미지, 모델 artifact 없음.
- 로컬 `models/Best_Age_Estimate_model_traced.pt`는 ignored 상태이며 commit 대상이 아닙니다.
- main 브랜치 직접 push가 아닙니다.

## Not Verified / Follow-up

- 실제 웹캠 GUI end-to-end는 사용자 환경에서 수동 QA가 필요합니다.
- 실제 PyQt 창에서 모델 파일 누락 오류 표시는 모델 파일이 현재 존재해 직접 확인하지 못했습니다.
- preview 테스트는 non-blank 회귀를 잡지만 stale-image 재사용 여부까지는 후속 강화 여지가 있습니다.
```
