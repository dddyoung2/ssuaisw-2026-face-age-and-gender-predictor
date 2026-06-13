# PR

## PR Title Suggestion

feat(app): integrate PyQt GUI with threaded camera flow

## Summary

- Connect `AgeEstimatorWindow` to `SystemController` as the main PyQt5 GUI entrypoint.
- Route camera start/stop, countdown, 40-frame capture, inference worker execution, result handling, and error recovery through controller/worker signals.
- Move GUI responsibilities toward display/input only, while camera capture and inference run through worker paths.
- Update result aggregation to return `success`, `valid_count`, and `reason` so GUI failure states are displayable.
- Add tests for result processing, camera detector behavior, and worker error/result paths.
- Document current architecture, development flow, agent/release ownership, and remaining manual QA/model follow-up.

## Major Changed Files

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

## Test Results

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS - 15 passed, 1 warning in 0.97s

경고:
.pytest_cache 경로 생성 권한 없음(PytestCacheWarning, WinError 5)

명령:
.\.venv\Scripts\python.exe -m py_compile src\face_age_gender_predictor\app\main_app.py src\face_age_gender_predictor\app\main_window.py src\face_age_gender_predictor\app\workers.py src\face_age_gender_predictor\camera\camera_detector.py src\face_age_gender_predictor\processing\result_processor.py

결과: PASS
```

## Security / Privacy Check

- [x] `.env`, `.env.*`, secret files, tokens, and private keys are not present in the changed/untracked file list.
- [x] Model files such as `*.pt`, `*.pth`, and `*.onnx` are not present in the changed/untracked file list.
- [x] Private image files are not present in the changed/untracked file list.
- [x] Build/cache artifacts such as `.pytest_cache`, `__pycache__`, `dist`, `build`, and egg-info output are not present in the non-ignored changed/untracked file list.
- [x] Current branch is `feature/gui-qthread-integration`, not `main`.

## BLOCKED or Follow-up

- Not blocked for PR: `AI-Agents/REVIEW.md` Verdict is `PASS`.
- Not verified in this environment: real desktop GUI launch, webcam preview, no-face behavior, face disappearing during countdown, 40-frame real capture stability, and actual camera/QThread cleanup on window close.
- Follow-up task: connect actual TorchScript model inference and naturally verify model-file-missing / TorchScript failure paths. Current worker/result/error contracts are prepared, but actual model connection is intentionally left for a separate task.
- Follow-up check: after the user pulls this branch, run manual QA on a desktop with a webcam and record the result.

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
