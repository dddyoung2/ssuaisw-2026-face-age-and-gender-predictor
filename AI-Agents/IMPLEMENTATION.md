# IMPLEMENTATION

## Summary

업로드된 PyQt5 GUI(`AgeEstimatorWindow`)를 기존 `SystemController` / `CameraBridgeWorker`
/ `InferenceWorker` / `result_processor` 흐름에 signal/slot으로 연결했다.

핵심 변경:

- 기본 실행 진입점 `app.main_app`을 `QCoreApplication`(콘솔) → `QApplication`(GUI)로 전환.
- `AgeEstimatorWindow`에서 `cv2.VideoCapture` 소유와 모든 `QTimer`(frame/countdown/
  collection/analysis), Haar cascade, heuristic 예측을 제거. GUI는 화면 표시와 버튼 입력만 담당.
- 카메라 읽기/얼굴 감지/40프레임 캡처는 `CameraThread`의 `CameraBridgeWorker` →
  `CameraDetector`에서 실행. 추론은 `InferenceThread`의 `InferenceWorker`에서 실행.
- `SystemController`가 GUI ↔ Worker 사이의 상태 전이와 signal 중계를 담당하는 허브가 됨.
- `result_processor`를 `docs/SPEC.md`의 success/valid_count/reason 계약(유효 30개 기준)으로 갱신.

작업 범위는 TASK의 "QThread 담당" 경계에 맞췄다. 실제 CNN 모델 호출(`CNNmodel.predict_frames`)
연결은 CNN/Inference 담당 범위라 이번 작업에서 손대지 않았고, `InferenceWorker`는 기존
임시 prediction 흐름을 유지하되 새 result 계약을 통과하도록만 연결했다. (아래 Risks 참고)

## Changed Files

- `src/face_age_gender_predictor/app/main_app.py`
  - `SystemController`를 GUI 허브로 재작성: GUI용 signal(status/state/face_ready/
    camera_running/measure_enabled/countdown/capture_progress/inference_progress/
    preview_frame/result_ready/error) 추가.
  - 카메라 Worker를 GUI "카메라 시작/종료" 버튼에 맞춰 lazy 생성/정리(`start_camera`,
    `stop_camera`, `_clear_camera_refs`).
  - 카운트다운 종료 시점 얼굴 재검증(`_on_countdown_finished`) 추가.
  - 성공/실패 result 분기(`on_inference_done`), 오류 복구(`on_error`,
    `_return_to_idle`), 종료 시 QThread `quit()/wait()` 정리(`shutdown`).
  - `QApplication` 기반 GUI 진입점 `main()` + `connect_window_and_controller()`.
  - 콘솔 흐름(`ConsoleCommandWorker`)은 기본 진입점에서 제거.
- `src/face_age_gender_predictor/app/main_window.py`
  - `AgeEstimatorWindow`를 View로 축소. 카메라/타이머/heuristic 제거.
  - GUI→Controller 입력 signal(`start_camera_requested`, `measurement_requested`,
    `stop_camera_requested`, `close_requested`) 추가.
  - Controller→GUI slot 추가(상태/프레임/진행률/결과/오류 표시). 미리보기 프레임은
    전달받은 프레임에 overlay만 그려 MainThread에서 렌더링.
  - `closeEvent`는 `close_requested`를 emit해 Controller가 정리하도록 위임.
- `src/face_age_gender_predictor/app/workers.py`
  - `CameraBridgeWorker`에 `preview_frame_ready(object)`, `capture_progress(int,int)`
    signal과 콜백 추가. 촬영 직전 얼굴 재검증 실패는 `error_occurred`로 전달.
  - `InferenceWorker`: 임시 prediction 흐름 유지(실제 모델은 타 역할), result 계약 연결.
  - `ConsoleCommandWorker`는 디버그용으로만 보존.
- `src/face_age_gender_predictor/camera/camera_detector.py`
  - `on_preview_frame(frame, box)`, `on_capture_progress(cur,total)`,
    `on_capture_aborted(reason)` 콜백 추가.
  - `_largest_face_box`(가장 큰 bbox 선택), `has_recent_face()`/`latest_face_box`
    (촬영 직전 재검증), `start_recording` 직전 재검증, 종료 중 캡처 중단 처리 추가.
- `src/face_age_gender_predictor/processing/result_processor.py`
  - `success`/`valid_count`/`reason` 포함 result dict 반환. 유효 prediction 필터링,
    `MIN_VALID_PREDICTIONS=30` 기준 성공/실패 처리.
- `tests/test_result_processor.py` — 새 계약(성공/실패/필터링/경계 30) 테스트로 갱신.
- `tests/test_camera_detector.py` (신규) — bbox 선택/재검증/촬영 중단 단위 테스트.
- `tests/test_workers.py` (신규) — InferenceWorker가 result 계약을 만들고 빈 frames 시
  오류를 보고하는지 테스트.

## Requirement Mapping

| Requirement | Result |
| --- | --- |
| GUI 코드 부착 | 완료. `app.main_app`이 `AgeEstimatorWindow`를 기본 창으로 띄움 |
| GUI와 SystemController signal 연결 | 완료. `connect_window_and_controller()`로 양방향 연결 |
| GUI MainThread에서 카메라/추론 실행 안 함 | 완료. 카메라/추론을 Worker로 이전, GUI는 표시만 |
| CameraWorker QThread 분리 | 완료. `CameraThread`의 `CameraBridgeWorker` |
| InferenceWorker QThread 분리 | 완료. `InferenceThread`의 `InferenceWorker` |
| signal payload 정리 | 완료. preview/capture_progress/result 계약 정리 |
| 측정 버튼 중복 클릭 방지 | 완료. `request_measurement` 상태 가드 + measure 버튼 비활성화 |
| 얼굴 재검증 | 완료. 카운트다운 종료 시점 + `start_recording` 직전 2중 검증 |
| 40프레임 캡처 후 Inference/result 연결 | 완료. frames_ready → InferenceWorker → result_processor |
| 결과/오류 GUI 표시 | 완료. 성공/실패 result, 오류 메시지 모두 GUI 표시 |
| 종료 정리 | 완료. `shutdown()`에서 카메라/추론 QThread `quit()/wait()` |
| 자동 테스트 유지/보강 | 완료. 6 → 14개 (result_processor/camera/worker) |

## Test Results

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: 14 passed in 1.20s

명령: .\.venv\Scripts\python.exe -m py_compile (변경 모듈 5개)
결과: OK

명령: QT_QPA_PLATFORM=offscreen 스모크 (window+controller 연결, 신호 구동)
결과: 모든 slot 존재/연결 확인, 성공 result로 나이("25세")/성별 라벨 갱신,
      실패 result/오류 메시지 처리, 버튼 상태 계산 정상. 크래시 없음.
```

## Manual QA

자동화가 어려운 실제 웹캠/GUI 흐름은 데스크톱 + 카메라 환경에서 수동 확인이 필요하다.
현재 개발 환경(헤드리스, 카메라 없음)에서는 offscreen 스모크까지만 수행했다.

- 정상 케이스: **미실행(수동 QA 필요)** — 카메라/디스플레이 환경에서
  `python -m face_age_gender_predictor.app.main_app` 실행 후 측정 흐름 확인 요망.
- 얼굴 없음: **미실행(수동 QA 필요)** — measure 버튼 비활성화/측정 거부 확인 요망.
- 카운트다운 중 얼굴 사라짐: **미실행(수동 QA 필요)** — 카운트다운 종료 시점
  재검증으로 오류 표시되는지 확인 요망(로직은 `_on_countdown_finished`에 구현됨).
- 모델 없음/추론 실패: **부분** — 현재 `InferenceWorker`는 임시 prediction이라
  실제 모델 미스 케이스를 자연 발생시키지 못함. 예외 발생 시 `error_occurred`로
  GUI 오류 표시되는 경로는 `test_workers.py`(빈 frames)로만 검증됨.
- 종료 처리: **부분** — `shutdown()` 로직과 offscreen 구성은 확인. 실제 카메라
  스레드 종료는 카메라 환경 수동 확인 요망.

## Risks / Blocked

- 실제 CNN 모델 연결 미수행(역할 경계): `InferenceWorker`는 여전히 임시
  prediction을 생성한다. 따라서 "모델 파일 없음/추론 실패 → GUI 오류" 시나리오를
  실제로 트리거하려면 CNN/Inference 담당의 `CNNmodel.predict_frames` 연결이 필요하다.
  데이터 계약(prediction/result)과 오류 전달 경로는 준비되어 있다.
- 미리보기 프레임 전송(`preview_frame_ready`)은 기존 SPEC signal 목록에 없던 추가
  항목이다. GUI 카메라 미리보기를 위해 필요해 추가했으며, 카메라 자원은 여전히
  CameraDetector 한 경로에서만 소유한다.
- `CameraDetector`는 내부적으로 `threading.Thread`(daemon)에서 프레임을 읽고
  Qt signal을 emit한다(기존 패턴 유지). Qt의 cross-thread queued emit은 안전하지만,
  실제 카메라 환경에서 프레임 전송 부하/지연은 수동 QA로 확인이 필요하다.
- 실제 웹캠/GUI 수동 QA가 아직 기록되지 않았다(헤드리스 환경 한계).

## Notes for Codex QA

집중 확인 요청:

1. 종료 안정성: `SystemController.shutdown()`의 `quit()/wait(3000)` 순서와
   `stop_camera_requested.emit()` 후 카메라 QThread 정리가 실제 환경에서 leak 없이
   끝나는지. (`closeEvent` → `close_requested` → `shutdown`, `aboutToQuit` 중복 호출은
   `_shutting_down` 플래그로 가드)
2. 얼굴 재검증 2중화: 카운트다운 종료(`_on_countdown_finished`)와
   `CameraDetector.start_recording` 직전(`has_recent_face`) 양쪽 검증이 의도대로
   동작하는지, 그리고 실패 시 재측정 가능한 IDLE로 복귀하는지.
3. 중복 방지: 측정 중(`COUNTDOWN/CAPTURING/ANALYZING`) measure 버튼 비활성화 +
   `request_measurement`/`_start_inference_worker` 상태 가드가 충분한지.
4. result 계약 변경 영향: `result_processor` 반환 형식 변경이 다른 소비자에 영향 없는지
   (현재 소비자는 `InferenceWorker` → `SystemController`뿐).
5. 역할 경계 판단: 실제 모델 연결을 이번 task에 포함해야 하는지, 별도 TASK로 둘지.
   (본 작업은 QThread 연결 범위로 한정함)

## Open Questions

- `InferenceWorker`의 실제 모델 호출 연결을 이번 통합에 포함할지 여부는 팀 합의 필요
  (team-tasks.md상 CNN model / Inference 담당 영역). 임의 확장하지 않고 질문으로 남김.
- 미리보기 프레임 signal(`preview_frame_ready`)을 SPEC signal 목록에 정식 반영할지.

## QA Fix Round

Codex QA `REVIEW.md` (Verdict: NEEDS_FIX)의 지적을 다음과 같이 반영했다.

### 수정한 지적과 변경 파일

- **P1(a) — 카메라 시작 실패 후 `camera_running`이 True로 남는 버그 (수정 완료)**
  - `src/face_age_gender_predictor/app/workers.py`:
    `CameraBridgeWorker`에 `started` signal을 추가하고, `start_camera()` 실패 시
    `detector` 참조를 제거한 뒤 `error_occurred`에 이어 `finished`도 emit하도록 변경.
  - `src/face_age_gender_predictor/app/main_app.py`:
    `start_camera()`에서 `camera_running=True`를 즉시 emit하지 않고, Worker의
    `started` signal을 받은 `_on_camera_started()`에서만 True로 만들도록 변경.
    `_clear_camera_refs()`는 정리 시 `camera_running`이 남아 있으면 False로 복구하고
    `camera_running_changed(False)`를 emit하도록 보강.
  - 검증(offscreen 스모크): 카메라 시작 실패 시 `camera_running=False`,
    `camera_thread=None`, "카메라 시작" 버튼 재활성화, 크래시 없음 확인.
    성공 경로에서는 `started` → `camera_running=True`로 정상 전환 확인.

- **P1(c) — 추론 실패/모델 없음 경로가 GUI 오류로 처리되는지 검증 부족 (자동 테스트 추가)**
  - `tests/test_workers.py`:
    `process_predictions`가 예외를 던지는 상황(모델 파일 없음 모사)을 monkeypatch로
    만들어, `InferenceWorker.run()`이 예외를 밖으로 전파하지 않고 `error_occurred`로
    전달하며 `finished`도 emit하는지 확인하는 테스트 추가.
    (실제 TorchScript 모델 로드 실패는 임시 prediction 구조상 자연 발생하지 않으므로
    아래 BLOCKED로 남김.)

- **P2(e) — `.gitignore`가 보고 산출물(IMPLEMENTATION.md/REVIEW.md)을 ignore (수정 완료)**
  - `.gitignore`: `AI-Agents/IMPLEMENTATION.md`, `AI-Agents/REVIEW.md` ignore 라인을
    제거해 Acceptance가 요구하는 완료 산출물로 커밋되도록 변경. `AI-Agents/archive/`는 유지.

- **P2(f) — README가 GUI 통합 전 콘솔 흐름으로 설명 (수정 완료)**
  - `README.md`: 프로젝트 개요·실행 방법·현재 상태를 GUI 진입점(`main_app`) 기준으로 갱신.

### 이미 해결되어 있던 지적

- **P2(d) — `.claude/settings.local.json` 커밋 제외**:
  현재 `.gitignore:21`의 `.claude/`가 이미 해당 파일을 ignore한다
  (`git check-ignore .claude/settings.local.json` → `.gitignore:21:.claude/` 확인).
  별도 변경 없이 충족.

### 재실행한 테스트

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: 15 passed (이전 14 → 추론 실패 경로 테스트 1건 추가)

명령: py_compile (main_app.py, workers.py)
결과: OK

스모크(QT_QPA_PLATFORM=offscreen):
- 카메라 시작 실패: camera_running=False, camera_thread=None, start 버튼 재활성화, 크래시 없음
- 카메라 시작 성공: started → camera_running=True 전환
```

### 아직 남은 BLOCKED 항목

- **P1(b) — 실제 웹캠/GUI 수동 QA 미실행**: 현재 개발 환경이 헤드리스(웹캠/디스플레이
  없음)라 정상 흐름·얼굴 없음·카운트다운 중 얼굴 사라짐·실제 종료 처리의 수동 QA를
  실행할 수 없다. 데스크톱+웹캠 환경에서 수행 후 본 문서에 기록 필요.
- **P1(c) 잔여 — 실제 모델 파일 없음/실제 추론 실패 경로**: `InferenceWorker`가 임시
  prediction을 사용하므로 실제 TorchScript 로드 실패를 자연 발생시킬 수 없다. 예외 →
  GUI 오류 전달 경로는 자동 테스트로 검증했으나, 실제 모델 연결은 CNN/Inference 담당
  범위(team-tasks.md)라 본 작업에서 제외한다. 모델 연결 시 동일 경로로 처리되도록 준비됨.

---

## QA Fix Round 2

Codex QA 2차 `REVIEW.md` (Verdict: NEEDS_FIX)의 지적을 다음과 같이 반영했다.
이번 REVIEW는 사용자 결정을 함께 반영했다: (a) 실제 웹캠/GUI 수동 QA는 사용자가
commit 후 pull 받아 직접 진행(Claude blocker 아님, Not Verified), (b) 실제 모델 파일
연결은 별도 task로 이관, (c) Claude는 PR 본문/PR.md를 작성하지 않고 `IMPLEMENTATION.md`
보고서만 작성.

### 수정한 지적과 변경 파일

- **P1 — 캡처 중 같은 `VideoCapture`를 두 스레드가 동시에 read하는 경합 (수정 완료)**
  - `src/face_age_gender_predictor/camera/camera_detector.py`:
    - `_read_lock`(`threading.Lock`)을 추가해 카메라 read를 직렬화.
    - `_detect_loop()`는 `_recording` 중에는 `_cap.read()`를 호출하지 않고 잠시 대기하도록
      변경(촬영 중 카메라는 `_record_frames()`가 단독으로 읽음).
    - `_detect_loop()`와 `_record_frames()`의 각 `_cap.read()` 호출을 `_read_lock`으로 감싸,
      촬영 시작 경계 순간에도 동시 read가 발생하지 않도록 보장.
  - 검증(스모크): 동시 read를 감지하는 FakeCap으로 detect loop 실행 중 40프레임 캡처를
    동시에 수행 → `concurrent read overlap detected: False`, 캡처 정상 완료 확인.

- **P2 — `docs/development.md` / `docs/architecture.md`가 `main_window.py`를 "단독
  프로토타입(QTimer/VideoCapture/heuristic 직접 포함)"으로 설명 (수정 완료)**
  - `docs/development.md`: 실행 섹션의 `main_window.py` 설명을 "View로 축소, main_app이
    최종 진입점" 기준으로 갱신.
  - `docs/architecture.md`: "현재 main_window.py 런타임 구성/데이터 흐름" 블록(REVIEW가
    지적한 :57-69, :102-113)을 통합 후 구조(View + CameraThread/InferenceThread 분리)로 갱신.

### Codex/user가 후속 정리한 지적

- **P2 — PR 작성 책임 문서 지시 / `AI-Agents/PR.md` stale (정리 완료)**:
  사용자가 "Claude는 PR을 쓰지 말고 보고서만 작성"으로 결정했다.
  이에 따라 `AGENTS.md`, `CLAUDE.md`, `AI-Agents/TASK.md`,
  `AI-Agents/ACCEPTANCE.md`, `AI-Agents/README.md`, `docs/team-tasks.md`,
  `AI-Agents/PR.md`를 정리해 Claude가 GitHub PR, PR 본문, `AI-Agents/PR.md`를
  작성하거나 갱신하지 않도록 차단했다. `AI-Agents/PR.md`의 stale PR 초안은 제거했고,
  사용자 또는 Codex Release 전용 릴리즈 참고 파일로 바꿨다.

- **실제 모델 파일 없음/TorchScript 실제 추론 실패**: 사용자 결정에 따라 별도 task로
  이관. 본 task에서 모델 연결을 확장하지 않았다.

### 재실행한 테스트

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: 15 passed

명령: py_compile (camera_detector.py)
결과: OK

스모크(동시 read 경합 검사):
FakeCap으로 detect loop + 40프레임 캡처 동시 실행 → concurrent read overlap = False,
캡처 40프레임 정상 완료, still recording = False.
```

### 아직 남은 Not Verified / BLOCKED 항목

- **실제 웹캠/GUI 수동 QA (Not Verified)**: 헤드리스 환경이라 실행 불가. 사용자가
  commit 후 pull 받아 실제 데스크톱+웹캠 환경에서 정상 흐름·얼굴 없음·카운트다운 중
  얼굴 사라짐·실제 40프레임 캡처 안정성·종료 시 카메라/QThread leak 여부를 직접 확인 예정.
  (Claude는 완료로 기록하지 않고 Not Verified로 남김.)
- **실제 모델 파일 없음/실제 추론 실패 경로 (별도 task)**: 위 분리 사유 참조.
