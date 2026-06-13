# TASK

## TL;DR

- 목표: 업로드된 PyQt5 GUI 코드를 현재 프로그램 흐름에 연결하고, 카메라/추론 Worker가 QThread 경로로 안정적으로 실행되며, `models/` 아래 TorchScript `.pt` 모델을 실제 추론 경로에 연결되도록 마무리한다.
- 범위: GUI와 SystemController 연결, signal/slot 정리, CameraBridgeWorker/InferenceWorker QThread 실행, `CNNmodel.py` 앱용 추론 API 연결, 종료 정리, QA 테스트.
- 수정 가능: `src/face_age_gender_predictor/app/`, `src/face_age_gender_predictor/inference/CNNmodel.py`, QThread/모델 연결에 필요한 Worker 연결부, 최소 테스트와 작업 기록 문서.
- 수정 금지: 모델 파일, 개인 이미지, 시크릿, 관련 없는 대규모 리팩터링.
- 테스트: pytest, GUI 수동 QA, 카메라/추론 오류와 종료 시나리오 확인.

## Goal

이번 작업의 목표는 업로드된 GUI가 기존 `SystemController`, `CameraBridgeWorker`, `InferenceWorker`, `CNNmodel.py`, `result_processor` 흐름을 통해 동작하도록 연결을 마무리하는 것이다. 사용자는 GUI에서 카메라 미리보기를 보고, 얼굴 준비 상태에서 측정 버튼을 눌러 카운트다운, 40프레임 캡처, TorchScript `.pt` 모델 추론 Worker 실행, 결과 또는 오류 표시까지 진행할 수 있어야 한다.

이번 작업자는 병합 범위 안에서 QThread 연결과 실제 모델 연결까지 함께 책임진다. 단, 모델 파일 자체 수정, 모델 재학습, 대규모 전처리 재작성은 하지 않는다.

## Requirements

- 업로드된 GUI 코드를 현재 `src/face_age_gender_predictor` 구조에 맞게 배치한다.
- GUI와 SystemController를 signal/slot으로 연결한다.
- GUI MainThread에서 카메라 루프나 모델 추론을 실행하지 않는다.
- CameraBridgeWorker는 CameraThread에서 실행한다.
- InferenceWorker는 InferenceThread에서 실행한다.
- CameraBridgeWorker와 InferenceWorker의 signal payload가 기존 SystemController 흐름과 맞도록 정리한다.
- `models/Best_Age_Estimate_model_traced.pt`를 기본 모델 경로로 사용한다.
- `CNNmodel.py`는 앱에서 import해도 샘플 추론이나 시각화가 자동 실행되지 않게 정리한다.
- `CNNmodel.py`에 앱용 추론 API를 제공한다. 권장 형태는 `predict_frames(frames: list) -> list[dict]`이다.
- InferenceWorker는 임시 prediction 대신 `CNNmodel.py`의 앱용 추론 API를 호출한다.
- 모델 파일 없음, 모델 로드 실패, 전처리 실패, 추론 실패는 앱 크래시가 아니라 `error_occurred` 또는 실패 result 경로로 GUI에 전달한다.
- 측정 버튼 클릭 후 중복 요청을 막는다.
- 카운트다운 종료 시점 또는 촬영 시작 직전에 얼굴 상태를 재검증한다.
- 40프레임 캡처 후 InferenceWorker/CNNmodel/result_processor 경로로 이어진다.
- 성공 결과와 실패 메시지를 GUI에 표시한다.
- 종료 시 카메라와 QThread가 정리된다.
- 가능한 자동 테스트를 유지하거나 보강한다.
- QA 수동 테스트 결과를 기록한다.
- 모델 성능 개선, 모델 재학습, 대규모 전처리 알고리즘 재작성은 하지 않는다.

## Target Files

수정 가능 파일:

- `src/face_age_gender_predictor/app/main_app.py`
- `src/face_age_gender_predictor/app/workers.py`
- GUI 코드가 들어갈 `src/face_age_gender_predictor/app/` 하위 파일
- `src/face_age_gender_predictor/camera/camera_detector.py` 중 QThread 연결과 캡처 요청 처리에 필요한 최소 부분
- `src/face_age_gender_predictor/inference/CNNmodel.py` 중 앱용 모델 로드/전처리/추론 API 연결에 필요한 부분
- `tests/` 중 상태 전이, Worker 연결, 모델 연결, 결과 처리 정책 확인에 필요한 테스트
- `AI-Agents/IMPLEMENTATION.md`

주의해서 다룰 파일:

- `src/face_age_gender_predictor/processing/result_processor.py`
- `pyproject.toml`
- `.github/workflows/tests.yml`
- `.github/pull_request_template.md`
- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/`
- `AI-Agents/TASK.md`
- `AI-Agents/ACCEPTANCE.md`
- `AI-Agents/PR.md` (Claude 수정 금지, 사용자 또는 Codex Release 관리)

수정 금지 파일:

- `.env`
- `.env.*`
- `models/*.pt`
- `models/*.pth`
- `models/*.onnx`
- 개인 이미지 또는 개인정보 포함 파일
- 관련 없는 파일

## Related Docs

- `docs/overview.md`
- `docs/SPEC.md`
- `docs/architecture.md`
- `docs/components.md`
- `docs/development.md`
- `docs/team-tasks.md`

## Out of Scope

- 모델 재학습
- 데이터셋 수집 또는 라벨링
- 대규모 UI 리디자인
- 얼굴 전처리 알고리즘 재작성
- 모델 성능 최적화 또는 출력 해석 정책 변경
- GitHub Actions 대규모 개편
- 팀 합의 없는 프로젝트 구조 재편
- prediction dict 또는 result dict 형식의 임의 변경
- 모델 파일 커밋

## Notes

- 기존 구조를 최대한 유지한다.
- GUI 코드는 MainThread, 카메라와 추론은 WorkerThread 원칙을 지킨다.
- QThread 연결과 실제 `.pt` 모델 연결 마무리에 집중한다.
- `CNNmodel.py`는 앱용 API 연결에 필요한 범위에서 수정한다.
- `result_processor.py`는 연결상 꼭 필요한 경우에만 최소 수정한다.
- 모델 파일(`models/*.pt`)은 읽어서 사용할 수 있지만 수정하거나 커밋 대상으로 만들지 않는다.
- 완료 기준 자체를 구현 중 임의로 바꾸지 않는다.
- Claude는 PR 본문이나 `AI-Agents/PR.md`를 작성/갱신하지 않는다.
- 불확실한 요구사항은 임의 확장하지 말고 `IMPLEMENTATION.md`나 `REVIEW.md`에 질문으로 남긴다.
