# Team Tasks

## 목적

이 문서는 5개 역할로 나뉜 팀 프로젝트에서 담당 범위와 작업 충돌을 줄이기 위한 역할 분담 기준이다. 실제 담당자 이름은 팀 합의 후 채운다.

## 역할 분담

| 역할 | 담당 범위 | 주요 파일 |
| --- | --- | --- |
| GUI 담당 | PyQt5 MainWindow, 카메라 화면 표시, 버튼/상태/결과 UI | GUI 파일, `src/face_age_gender_predictor/app/` |
| QThread 담당 | MainThread/WorkerThread 분리, signal/slot 연결, 스레드 종료 정리 | `main_app.py`, `workers.py` |
| CNN model 구축 담당 | TorchScript 모델 구성, 모델 파일 로드 정책, 모델 출력 형식 정리 | `CNNmodel.py`, `models/` |
| Inference/Camera 담당 | 카메라 감지, 40프레임 캡처, InferenceWorker 연결, prediction 생성 흐름 | `camera_detector.py`, `workers.py`, inference 연결부 |
| 전처리 담당 | 얼굴 검출/정렬/crop/resize/normalize 등 모델 입력 전처리 | `CNNmodel.py`, 전처리 helper, 관련 테스트 |

## 역할 간 인터페이스

| 경계 | 합의해야 하는 인터페이스 |
| --- | --- |
| GUI ↔ QThread/SystemController | 버튼 요청 signal, 상태/카운트다운/결과 표시 signal |
| QThread ↔ Camera | `start_camera`, `start_capture`, `frames_ready`, `error_occurred` |
| Camera ↔ Inference | `frames: list[np.ndarray]`, 40프레임 기준, 캡처 실패 처리 |
| 전처리 ↔ CNN model | 모델 입력 tensor shape, normalize 기준, 실패 시 `None` 또는 예외 정책 |
| CNN model ↔ result_processor | prediction dict 형식 |
| result_processor ↔ GUI | success/failure result dict 형식 |

## 합의가 필요한 영역

- `SystemController` 상태 전이 변경
- Worker signal 이름과 payload 변경
- prediction dict 형식 변경
- result dict 형식 변경
- 모델 파일 경로 변경
- GUI와 Worker 사이의 연결 방식 변경
- 전처리 실패를 prediction 제외로 볼지 전체 실패로 볼지에 대한 정책
- 여러 얼굴 감지 시 대상 얼굴 선택 기준

## 현재 우선 작업

1. GUI 코드를 현재 패키지 구조에 부착한다.
2. GUI와 SystemController signal을 맞춘다.
3. CameraWorker와 InferenceWorker를 QThread에서 안정적으로 실행한다.
4. 정상/오류/종료 QA를 수행한다.

## 작업 전환 규칙

- 새 작업은 `AI-Agents/TASK.md`에 목표와 범위를 먼저 적는다.
- 완료 기준은 `AI-Agents/ACCEPTANCE.md`에 체크리스트로 둔다.
- 구현자는 `AI-Agents/IMPLEMENTATION.md`에 결과를 기록한다.
- QA 담당은 `AI-Agents/REVIEW.md`에 판정을 남긴다.
- PR 준비와 `AI-Agents/PR.md` 관리는 사용자 또는 Codex Release 담당만 수행한다.
- Claude Code는 PR 본문, GitHub PR, `AI-Agents/PR.md`를 작성하거나 갱신하지 않는다.
