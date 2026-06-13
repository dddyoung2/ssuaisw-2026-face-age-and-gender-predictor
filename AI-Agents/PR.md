# PR

## PR 제목 제안

feat(app): PyQt GUI와 QThread 카메라 흐름 통합

## 변경 요약

- `AgeEstimatorWindow`를 `SystemController`와 연결해 PyQt5 GUI를 기본 실행 진입점으로 구성했습니다.
- 카메라 시작/종료, 카운트다운, 40프레임 캡처, 추론 Worker 실행, 결과 표시, 오류 복구를 controller/worker signal 흐름으로 정리했습니다.
- GUI는 화면 표시와 버튼 입력을 담당하고, 카메라 캡처와 추론 흐름은 Worker 경로에서 실행되도록 책임을 분리했습니다.
- `result_processor`가 `success`, `valid_count`, `reason`을 포함한 결과 dict를 반환하도록 갱신해 GUI에서 실패 상태를 표시할 수 있게 했습니다.
- result processor, camera detector, worker 오류/결과 경로 테스트를 추가했습니다.
- README, 개발/아키텍처 문서, AI agent 작업 문서를 현재 릴리즈 경계에 맞게 정리했습니다.

## 주요 변경 파일

- `src/face_age_gender_predictor/app/main_app.py`
- `src/face_age_gender_predictor/app/main_window.py`
- `src/face_age_gender_predictor/app/workers.py`
- `src/face_age_gender_predictor/camera/camera_detector.py`
- `src/face_age_gender_predictor/processing/result_processor.py`
- `tests/test_result_processor.py`
- `tests/test_camera_detector.py`
- `tests/test_workers.py`
- `AI-Agents/TASK.md`
- `AI-Agents/ACCEPTANCE.md`
- `AI-Agents/IMPLEMENTATION.md`
- `AI-Agents/REVIEW.md`
- `README.md`
- `CONTRIBUTING.md`
- `docs/architecture.md`
- `docs/components.md`
- `docs/development.md`
- `docs/overview.md`
- `docs/SPEC.md`
- `docs/team-tasks.md`

## 테스트 결과

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS - 15 passed, 1 warning in 0.97s

경고:
.pytest_cache 경로 생성 권한 없음(PytestCacheWarning, WinError 5)

명령:
.\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_app.py src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\app\workers.py src\face_age_gender_predictor\camera\camera_detector.py src\face_age_gender_predictor\processing\result_processor.py

결과: PASS
```

## 보안/개인정보 확인

- [x] `.env`, `.env.*`, secret 파일, token, private key가 변경/추가 파일 목록에 없습니다.
- [x] `*.pt`, `*.pth`, `*.onnx` 같은 모델 파일이 변경/추가 파일 목록에 없습니다.
- [x] 개인 이미지 파일이 변경/추가 파일 목록에 없습니다.
- [x] `.pytest_cache`, `__pycache__`, `dist`, `build`, egg-info 같은 빌드/캐시 산출물이 non-ignored 변경 목록에 없습니다.
- [x] 현재 브랜치는 `feature/gui-qthread-integration`이며 `main` 브랜치 직접 push가 아닙니다.

## 남은 확인 / 후속 작업

- PR 진행 자체를 막는 blocker는 없습니다. `AI-Agents/REVIEW.md` Verdict는 `PASS`입니다.
- 현재 환경에서는 실제 데스크톱 GUI 실행, 웹캠 미리보기, 얼굴 없음 상태, 카운트다운 중 얼굴 이탈, 실제 40프레임 캡처 안정성, 창 종료 시 카메라/QThread 정리를 검증하지 못했습니다.
- 실제 TorchScript 모델 연결과 모델 파일 없음/추론 실패 자연 발생 검증은 별도 task로 이관했습니다.
- 사용자가 노트북에서 이 브랜치를 pull 받은 뒤 실제 웹캠 환경에서 수동 QA를 진행하고 결과를 기록해야 합니다.

## Suggested PR Body

```markdown
## 변경 요약
- PyQt5 GUI를 `main_app.py`의 기본 실행 진입점으로 연결했습니다.
- GUI 버튼 입력과 상태/결과 표시를 `SystemController` signal/slot 흐름에 연결했습니다.
- 카메라 시작/종료, 카운트다운, 40프레임 캡처, 추론 Worker 실행, 결과/오류 복구 흐름을 정리했습니다.
- `result_processor`가 `success`, `valid_count`, `reason`을 포함한 결과 계약을 반환하도록 갱신했습니다.
- result/camera/worker 자동 테스트를 보강했습니다.
- README, 개발/아키텍처 문서, AI agent 작업 문서를 현재 릴리즈 경계에 맞춰 정리했습니다.

## 테스트
- [x] `.\.venv\Scripts\python.exe -m pytest -q`
  - `15 passed, 1 warning`
  - 경고: `.pytest_cache` 쓰기 권한 없음
- [x] `.\.venv\Scripts\python.exe -m py_compile ...`

## 보안/개인정보 확인
- `.env`, 시크릿, 모델 파일, 개인 이미지, 빌드/캐시 산출물은 커밋 대상에 없습니다.
- 현재 브랜치는 `feature/gui-qthread-integration`이며 `main` 직접 push가 아닙니다.

## Not Verified / Follow-up
- 실제 데스크톱 GUI 실행과 웹캠 수동 QA는 이 환경에서 검증하지 못했습니다.
- 실제 TorchScript 모델 연결과 모델 파일 없음/추론 실패 자연 발생 검증은 별도 task로 이관합니다.
- 사용자가 pull 받은 뒤 실제 웹캠 환경에서 정상 흐름, 얼굴 없음, 카운트다운 중 얼굴 사라짐, 종료 처리를 확인해야 합니다.
```
