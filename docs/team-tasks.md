# Team Tasks

## 목적

이 문서는 팀 프로젝트에서 역할 범위와 작업 충돌을 줄이기 위한 기준이다. 실제 담당자 이름은 팀에서 별도로 정한다.

## 역할 분담

| 역할 | 담당 범위 | 주요 파일 |
| --- | --- | --- |
| GUI 담당 | PyQt5 화면, 버튼, 상태, 결과 표시 | `src/face_age_gender_predictor/app/main_window.py` |
| Controller/QThread 담당 | 상태 전이, signal/slot 연결, thread 생성과 종료 | `src/face_age_gender_predictor/app/main_app.py`, `src/face_age_gender_predictor/app/workers.py` |
| Camera 담당 | 웹캠 읽기, 얼굴 감지, 40프레임 캡처 | `src/face_age_gender_predictor/camera/camera_detector.py` |
| Inference 담당 | 모델 API 호출, 추론 Worker 연결, prediction 생성 | `src/face_age_gender_predictor/app/workers.py`, `src/face_age_gender_predictor/inference/CNNmodel.py` |
| Model/Preprocess 담당 | TorchScript 모델 로드, 얼굴 전처리, 입력 tensor 구성 | `src/face_age_gender_predictor/inference/CNNmodel.py`, `models/` |
| Processing/QA 담당 | 결과 집계, 테스트, 수동 QA 기준 | `src/face_age_gender_predictor/processing/result_processor.py`, `tests/`, `docs/` |

## 역할 간 인터페이스

| 경계 | 합의해야 하는 인터페이스 |
| --- | --- |
| GUI <-> Controller | 버튼 요청 signal, 상태/카운트다운/진행률/결과 표시 signal |
| Controller <-> Camera | `start_camera`, `start_capture`, `frames_ready`, `error_occurred` |
| Camera <-> Inference | `frames: list[np.ndarray]`, 40프레임 기준, 캡처 실패 처리 |
| Preprocess <-> Model | 모델 입력 tensor shape, normalize 기준, 실패 시 예외/None 정책 |
| Model <-> result_processor | prediction dict 형식 |
| result_processor <-> GUI | success/failure result dict 형식 |

## 합의가 필요한 변경

- `SystemController` 상태 전이 변경
- Worker signal 이름 또는 payload 변경
- prediction dict 형식 변경
- result dict 형식 변경
- 모델 파일 경로 변경
- GUI와 Worker 사이 연결 방식 변경
- 전처리 실패를 prediction 제외로 볼지 전체 실패로 볼지에 대한 정책 변경
- 여러 얼굴 감지 시 대표 얼굴 선택 기준 변경
- 반복 측정 시 이전 결과를 언제 초기화할지에 대한 정책 변경

## 현재 우선 작업

1. GUI, Controller, CameraWorker, InferenceWorker 연결 상태 유지
2. 모델 파일 경로와 추론 API 계약 유지
3. 얼굴 인식 민감도와 재측정 흐름을 수동 QA로 확인
4. 실제 웹캠 환경에서 정상/실패/종료 시나리오 검증
5. 문서와 테스트가 현재 구현과 다르지 않도록 유지

## 작업 전환 규칙

- 새 작업은 `AI-Agents/TASK.md`의 목표와 범위를 먼저 확인한다.
- 완료 기준은 `AI-Agents/ACCEPTANCE.md` 체크리스트로 확인한다.
- 구현자는 `AI-Agents/IMPLEMENTATION.md`에 결과를 기록한다.
- QA 담당자는 `AI-Agents/REVIEW.md`에 판정을 남긴다.
- PR 준비와 `AI-Agents/PR.md` 관리는 사용자 또는 Codex Release 담당만 수행한다.
- Claude Code는 GitHub PR, PR 본문, `AI-Agents/PR.md`를 작성하거나 갱신하지 않는다.
