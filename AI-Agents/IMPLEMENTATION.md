# IMPLEMENTATION

Status: IMPLEMENTED (실제 `.pt` 모델 로드/추론 검증 완료 — 단, 이 머신의 GUI 경로는
torch/PyQt5 DLL 충돌로 막힘; 실제 웹캠 수동 QA는 사용자 환경에서 진행)

> 보고서 형식 안내: CLAUDE.md의 표준 형식(Summary / Changed Files / Requirement
> Mapping / Test Results / Risks / Blocked / Notes for Codex QA)에 더해 `Not Verified`,
> `Open Questions` 섹션을 추가했다.
> - `Not Verified`: TASK의 "Test / Verification Expectations"가 실제 `.pt` 모델 가시성
>   여부와 실모델 추론 검증 여부를 명시적으로 기록하라고 요구해, Risks와 분리해
>   "검증 못 한 것"을 한눈에 보이게 하려는 의도다.
> - `Open Questions`: TASK "Notes for Implementer"가 불확실한 요구사항을 임의 확장하지
>   말고 질문으로 남기라고 해서, 사용자 결정이 필요한 항목(torch/PyQt5 DLL 충돌 처리
>   방식)을 별도로 분리했다.
> 표준 형식만 유지하길 원하면 두 섹션을 `Risks / Blocked`로 합치면 된다.

## Summary

TASK의 세 가지 목표를 구현했다.

1. **재측정 루프 복구**: 한 번 성공/실패한 뒤 앱을 재시작하지 않고 다시 측정할 수
   있도록 카메라 감지 재개 회귀 버그를 수정했다.
2. **실제 `.pt` 모델 연동**: `CNNmodel.py`를 import-안전한 추론 모듈로 재작성하고
   `predict_frames()` API를 추가했다. `InferenceWorker`가 임시 random 예측 대신
   `CNNmodel.predict_frames(self.frames)`를 호출한다.
3. **QThread 분리 유지**: 모델 로드/전처리/추론은 `InferenceThread`의
   `InferenceWorker`에서만 실행되고, GUI MainThread는 표시 갱신만 담당한다.

핵심 재측정 버그의 원인은 `CameraDetector.resume_detection()`이었다. 촬영이 끝나면
`_record_frames()`가 이미 `_detecting=True`로 되돌려 놓기 때문에, 기존
`resume_detection()`은 "이미 감지 중"으로 보고 조기 return하여 안정화 캐시
(`_last_face_ready` 등)를 초기화하지 않았다. 그 결과 `_last_face_ready`가 직전 측정
시점의 `True`로 남아, 재개 후 얼굴이 그대로 있어도 "상태 변화 없음"으로 간주되어
`on_single_person_detected` 콜백이 다시 발생하지 않았고, 컨트롤러의 `face_ready`가
갱신되지 않아 측정 버튼이 재활성화되지 않았다.

## Changed Files

- `src/face_age_gender_predictor/inference/CNNmodel.py` (재작성)
  - import 시점 부작용 제거: 모듈 import만으로는 모델 로드, 샘플 이미지 읽기,
    샘플 추론, 최종 결과 print, matplotlib 창 띄우기를 하지 않는다. (Cell 1/2/3 및
    `import matplotlib`, 모듈 레벨 `torch.jit.load`, 샘플 이미지 경로 제거)
  - 공개 API `predict_frames(frames, model_path=None, progress_callback=None) -> list[dict]`
    추가. 각 dict는 `age/gender/age_probs/gender_confidence` 키를 가져
    `result_processor`와 호환된다.
  - `get_default_model_path()`로 repo 루트 기준
    `models/Best_Age_Estimate_model_traced.pt` 경로를 cwd와 무관하게 해석
    (`Path(__file__).resolve().parents[3]`).
  - `load_model()`은 파일 존재를 먼저 확인하고, 없으면 기대 경로를 명시한
    `FileNotFoundError`를 발생시킨다. torch/torchvision/mediapipe는 추론 시점에만
    지연 import된다. 로드된 모델은 `_get_cached_model()`로 캐시해 반복 측정 시 재로드를
    피한다.
  - torch에 직접 의존하는 구간은 `_run_model()` 하나로 격리했다(테스트에서 torch 없이
    집계/skip/progress 로직을 검증할 수 있게 하기 위함). 기존 전처리 함수
    (`detect_and_align`, `_rotate_by_eyes`, `FacePreprocessor`)와 학습/데이터셋용
    `AFADPreprocessor`는 유지했다(추론 경로에서는 사용하지 않음, mediapipe/tqdm는 지연 import).

- `src/face_age_gender_predictor/app/workers.py`
  - `InferenceWorker.run()`이 임시 random 예측 루프 대신
    `predict_frames(self.frames, progress_callback=...)`를 호출하도록 교체.
  - 더 이상 쓰지 않는 `random`, `time` import 제거.
  - 모델/전처리/추론 예외는 기존 try/except로 `error_occurred`에 전달하고 `finished`도
    항상 emit한다(임의 fallback 예측을 생성하지 않음).

- `src/face_age_gender_predictor/camera/camera_detector.py`
  - `resume_detection()`이 이미 감지 중이어도 안정화 캐시를 항상 초기화하도록 수정
    (재측정 회귀 버그 수정). 동작 로그만 구분.

- `tests/test_workers.py` (갱신)
  - `predict_frames`를 monkeypatch해 실제 `.pt` 없이 위임/계약/진행률을 검증.
  - 모델 전역 오류(`predict_frames` 예외) 및 후처리 예외가 모두 `error_occurred` +
    `finished`로 라우팅되는지 검증.

- `tests/test_camera_detector.py` (갱신)
  - `resume_detection()`이 이미 감지 중이어도 안정화 캐시를 초기화하는지 회귀 테스트 추가.

- `tests/test_cnnmodel.py` (신규)
  - import 무부작용, 기본 모델 경로 해석, 모델 파일 없음 오류 메시지, `predict_frames`
    데이터 계약, 전처리 실패 프레임 skip, 빈 입력 처리 검증.

- `tests/test_controller.py` (신규)
  - 성공/실패 후 IDLE 복귀 + `resume_detection_requested` emit, 재감지 후 측정 버튼
    재활성화, 2차 측정 시작(COUNTDOWN), 측정 중 중복 요청 무시 검증.

> 참고: `AI-Agents/ACCEPTANCE.md`, `AI-Agents/TASK.md`, `AI-Agents/PR.md`,
> `AI-Agents/REVIEW.md`, `scripts/test_run.py`는 이 작업 이전부터 working tree에 수정
> 상태로 있었으며 이번 작업에서 건드리지 않았다. (`PR.md`는 역할 경계상 Claude가 수정하지 않음)

## Requirement Mapping

### 1. 재측정(Re-Measurement)

- 성공 후 자동 감지 재개: `SystemController._return_to_idle()`이 카메라 실행 중이면
  `resume_detection_requested`를 emit → `CameraBridgeWorker.resume_detection()` →
  `CameraDetector.resume_detection()`. **resume_detection 캐시 초기화 버그를 수정**하여
  재개 후 얼굴이 그대로여도 `face_ready` 콜백이 다시 발생한다. (test_controller,
  test_camera_detector)
- 완료 직후 측정 버튼 비활성화 → 얼굴 재감지 시 재활성화:
  `_emit_measure_enabled()` = `camera_running and face_ready and state==IDLE`.
  완료 직후 `face_ready=False`로 비활성화, 재감지 시 `True`로 재활성화. (test_controller)
- 이전 결과 표시 유지 / 새 측정 시작 시 초기화: `main_window`는 재감지(`face_ready`)
  시 미리보기를 지우지 않고, 새 측정 진입(COUNTDOWN)에서만
  `reset_progress_bar()` + `clear_preview_panel()`을 호출한다. (기존 GUI 로직 유지)
- 실패/재시도 복구: `on_error()` → `_return_to_idle()` 동일 경로. (test_controller)
- 2차 측정 가능: 1차 성공 → 재감지 → `request_measurement()`가 COUNTDOWN 진입.
  (test_controller)

### 2. 실제 `.pt` 모델 연동

- import 안전성, lazy load, 경로 해석, 모델 없음 오류, 캐시: 위 Changed Files 참조.
  (test_cnnmodel)
- `InferenceWorker`가 `predict_frames` 위임: (test_workers)
- prediction dict 계약 및 `result_processor` 호환: `age/gender/age_probs/
  gender_confidence`. (test_cnnmodel, test_workers)
- 전처리 실패 프레임 skip → `result_processor`가 유효 수로 성공/실패 판정. 전역 오류는
  예외로 전파되어 `error_occurred`로. (test_cnnmodel, test_workers)

### 3. QThread / Threading

- 모델 로드/전처리/추론은 `InferenceWorker.run()`(InferenceThread)에서만 실행. GUI는
  표시만. 40프레임 캡처는 `CameraDetector`(카메라 워커 경로). (offscreen 스모크로
  `frames_ready → _start_inference_worker → InferenceWorker@QThread` 확인)
- 추론 종료 후 `inference_thread`/`inference_worker` 참조 정리(`_clear_inference_refs`),
  종료 시 `shutdown()`이 thread quit/wait. (기존 구조 유지, 스모크 확인)

## Test Results

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS — 30 passed in 0.27s

명령: .\.venv\Scripts\python.exe -m py_compile \
      src/face_age_gender_predictor/inference/CNNmodel.py \
      src/face_age_gender_predictor/app/workers.py \
      src/face_age_gender_predictor/app/main_app.py \
      src/face_age_gender_predictor/camera/camera_detector.py
결과: PASS

명령: QT_QPA_PLATFORM=offscreen 스모크 (GUI<->controller 연결,
      frames_ready→_start_inference_worker가 InferenceThread+InferenceWorker 생성, shutdown)
결과: PASS — InferenceThread is QThread, worker.frames=40, shutdown OK
```

모든 자동 테스트는 실제 `.pt` 모델 파일 없이 통과한다(모델/전처리/torch는 monkeypatch).

## Not Verified

> 갱신(QA Fix Round 3): `models/Best_Age_Estimate_model_traced.pt`가 이제 repo 루트에
> 존재한다(초기 작성 시점에는 없었음). 실제 모델 로드/출력 형태/dict 계약은 검증 완료.
> 아래 "Real Model Verification"과 "QA Fix Round 3" 참조.

- **실제 웹캠 + mediapipe 얼굴 검출 경로**: 실제 얼굴이 담긴 프레임에서
  `detect_and_align`이 얼굴을 검출/정렬하는 동작은 샘플 얼굴 이미지가 없어 자동으로는
  검증하지 못했다(웹캠 수동 QA 영역). 모델 forward 계약 자체는 검증됨.
- **실제 웹캠 GUI 수동 QA**: 카메라 미리보기, 카운트다운, 40프레임 캡처, 결과 표시,
  창 종료 시 카메라/스레드 해제의 실제 동작은 수동 QA 영역으로 남는다.

## Real Model Verification (QA Fix Round 3)

`models/Best_Age_Estimate_model_traced.pt`로 실제 추론을 검증했다(PyQt5 미로딩 독립
프로세스에서 실행 — 아래 DLL 충돌 회피).

```text
명령: python -c "CNNmodel.load_model(); _run_model(model, device, random 224x224)"
결과: PASS
- load_model() 성공, device=cpu
- 모델 출력 4개:
    out[0] predicted_age        torch.Size([1])
    out[1] predicted_gender     torch.Size([1])
    out[2] age_probs            torch.Size([1, 26])   # 26개로 평탄화, 합=1.0
    out[3] gender_confidence    torch.Size([1])
- predict_frames dict 계약 정상: age≈29.6, gender=1.0, gender_confidence≈0.675,
  age_probs 26개(합 1.0)
```

→ TASK/노트북 샘플의
`predicted_age, predicted_gender, age_probs, gender_confidence = model(input_tensor)`
계약과 실제 모델 출력이 **일치함을 확인**했다(이전의 "출력 형태 가정"은 검증됨).

## Risks / Blocked

- **(중요) Windows DLL 로드 충돌 — torch vs PyQt5**: 현재 머신에서 `PyQt5`를 먼저
  import한 뒤 `torch`를 import하면 `OSError [WinError 1114] c10.dll ... DLL 초기화
  루틴 실패`가 발생한다(torch 단독, cv2→torch, mediapipe→torch는 정상). torch 에러
  메시지는 "Microsoft Visual C++ Redistributable이 설치되어 있지 않을 수 있다"고
  안내한다. `app.main_app`은 PyQt5를 먼저 로드하므로, **이 머신에서는 실제 추론 시
  torch 로드가 실패할 수 있다.** 이때 예외는 `InferenceWorker`가 잡아
  `error_occurred`로 GUI에 전달하므로 앱이 크래시하지는 않지만, 실제 측정은
  실패한다.
  - **갱신(Round 3)**: 모델 파일이 존재하는 지금, 이 DLL 충돌이 **이 머신에서 GUI
    실제 추론을 막는 실질적 블로커**다. 재현 확인: PyQt5를 먼저 import한 뒤 실제
    모델을 로드하면 `WinError 1114`로 실패한다(반면 PyQt5 미로딩 시 모델 로드/추론은
    정상). 사용자의 실제 환경에서도 동일하게 막히는지 확인이 필요하다.
  - 권장 해결책(우선): 최신 MS Visual C++ x64 Redistributable 설치
    (https://aka.ms/vs/17/release/vc_redist.x64.exe).
  - 대안: 엔트리포인트에서 PyQt5보다 먼저 `import torch`를 수행하면 본 환경에서는
    정상 로드됨을 확인했다(`import torch; import PyQt5` → ok). 다만 이는 환경 의존
    워크어라운드이자 GUI 시작 시 torch를 즉시 로드하므로, 코드 적용 여부는 사용자
    결정이 필요하다(이번에도 임의 적용하지 않음).
- **모델 출력 형태 가정 → 검증 완료(Round 3)**: TASK/노트북 샘플의
  `predicted_age, predicted_gender, age_probs, gender_confidence = model(input_tensor)`
  계약이 실제 모델 출력과 일치함을 확인했다(`[1], [1], [1,26], [1]`). `age_probs`는
  1차원 26개로 평탄화되며 합이 1.0이다. (`_as_float`/`_as_float_list`는 텐서/배열 모두
  허용하도록 방어적으로 변환)
- `gender`는 result_processor가 0~1 원시값 평균 후 0.5 임계로 0/1을 정하는 계약이라,
  프레임별 클래스 인덱스(0/1)를 그대로 넣으면 다수결과 동일하게 동작한다.

## Notes for Codex QA

집중 확인 요청:

1. **재측정 회귀 픽스 정확성**: `CameraDetector.resume_detection()`이 이미 감지 중일
   때도 안정화 캐시를 초기화하는 변경이 의도대로 동작하는지, 그리고 실제 웹캠에서
   `측정1 성공 → 자동 재감지 → 버튼 재활성화 → 측정2 성공`이 재시작 없이 되는지.
2. **이전 결과 보존 규칙**: 재감지 시 이전 결과/미리보기가 유지되고, 새 측정 시작
   (COUNTDOWN)에서만 초기화되는지(GUI 수동 확인).
3. **모델 파일 없음 GUI 경로**: `models/Best_Age_Estimate_model_traced.pt`가 없을 때
   GUI에 명확한 오류가 뜨고 앱이 크래시하지 않는지.
4. **torch/PyQt5 DLL 충돌**: 위 Risks 항목. 사용자 실제 환경에서 VC++ Redistributable
   설치 후 실제 추론이 되는지, 안 되면 엔트리포인트 import 순서 조정이 필요한지.
5. **QThread 경계**: 실제 측정 중 GUI가 멈추지 않는지, 추론 종료 후 thread/worker
   참조가 정리되고 창 종료 시 카메라가 해제되는지(실환경 수동 QA).

## Open Questions

- torch/PyQt5 DLL 충돌 해결을 코드(엔트리포인트 import 순서)로 흡수할지, 환경 설정
  (VC++ Redistributable)으로 둘지에 대한 사용자 결정이 필요하다. 이번 범위에서는
  코드 변경 없이 보고만 했다.

## QA Fix Round (Codex REVIEW NEEDS_FIX 대응)

`AI-Agents/REVIEW.md`의 NEEDS_FIX 4건에 대한 대응 결과.

### Finding 1 — 촬영 직전 재검증이 grace period로 통과될 수 있음 → 수정함

- 원인: `start_recording()`이 `has_recent_face()`(grace period 1.2초 포함)로 직전
  재검증을 수행해, 얼굴이 방금 사라진 상태에서도 40프레임 캡처가 시작될 수 있었다.
- 수정: 현재 프레임의 유효 bbox만 보는 `has_current_face()`(grace 미적용)를 추가하고,
  `start_recording()`의 직전 재검증을 `has_current_face()` 기준으로 변경했다. grace
  period(`has_recent_face`)는 감지/버튼 상태 안정화(깜빡임 방지) 용도로만 유지한다.
- 파일: `src/face_age_gender_predictor/camera/camera_detector.py`
- 테스트: `tests/test_camera_detector.py`에 회귀 테스트 2건 추가
  (`test_has_current_face_ignores_grace_period`,
  `test_start_recording_aborts_when_only_grace_period_face`).

### Finding 2 — 전처리 예외가 모두 삼켜져 critical 실패가 GUI error path로 안 감 → 수정함

- 원인: `predict_frames()`가 `detect_and_align()`의 모든 `Exception`을 잡아
  `face_rgb=None`으로 처리해, mediapipe/opencv import·런타임 오류 같은 치명적 실패도
  빈 prediction(skip)으로 숨겨졌다.
- 수정: `predict_frames()`의 blanket try/except를 제거했다. 얼굴 미검출은
  `detect_and_align()`이 예외가 아니라 `None`을 반환하므로 기존대로 skip되고, 치명적
  예외는 그대로 전파되어 `InferenceWorker.run()`의 except에서 `error_occurred`로
  라우팅된다.
- 파일: `src/face_age_gender_predictor/inference/CNNmodel.py`
- 테스트: `tests/test_cnnmodel.py`에 회귀 테스트 1건 추가
  (`test_predict_frames_propagates_critical_preprocessing_error`). 기존
  `test_predict_frames_skips_unpreprocessable_frames`(None skip)와 함께 두 경로를 구분 검증.

### Finding 3 — 금지/경계 파일 `AI-Agents/PR.md` 수정됨 → 건드리지 않음(경계 준수)

- 이 변경은 이번 구현에서 내가 만든 것이 아니다. 세션 시작 시점에 이미 working tree에
  존재한 변경이며, 내용은 HEAD의 기존 PR 초안을 제거하고
  "Claude Code must not write or update this file" 플레이스홀더로 **교체**하는 것이다.
  즉 경계를 위반하는 변경이 아니라 오히려 경계를 강제하는 변경이다.
- CLAUDE.md/AGENTS.md 및 수정 규칙 4(수정 금지 파일을 건드리지 않는다)에 따라 Claude는
  `PR.md`를 수정하지 않는다. 이를 HEAD로 되돌리면 오히려 과거 Claude 작성 PR 초안이
  복원되어 경계와 더 어긋난다.
- 조치: **수정하지 않음.** `PR.md` 정리는 사용자 또는 Codex Release 담당의 결정 사항으로
  남긴다.

### Finding 4 — `TASK.md`/`ACCEPTANCE.md` 대규모 변경됨 → 건드리지 않음(작업 정의 보존)

- 이 변경도 내가 만든 것이 아니다. 세션 시작 전 이미 working tree에 존재했다. working
  tree의 `TASK.md`/`ACCEPTANCE.md`는 **이번에 내가 구현한 바로 그 태스크(재측정 루프 +
  실제 `.pt` 연동)의 정의**이고, HEAD 버전은 이전(완료된) GUI 통합 태스크의 정의다.
- 이를 HEAD로 되돌리면 방금 구현한 태스크의 요구사항/완료조건 자체가 사라진다(파괴적).
  내가 작성하지 않았고, 되돌리면 사용자가 의도한 태스크 정의가 손실되므로 임의로
  수정하지 않는다.
- 조치: **수정하지 않음.** 이 문서들이 사용자 승인 범위인지 확인/정리하는 것은 사용자
  결정 사항으로 남긴다.

### QA Fix Round 테스트 결과

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS — 33 passed in 0.28s  (기존 30 + 회귀 3)

명령: .\.venv\Scripts\python.exe -m py_compile \
      src/face_age_gender_predictor/inference/CNNmodel.py \
      src/face_age_gender_predictor/camera/camera_detector.py \
      src/face_age_gender_predictor/app/workers.py
결과: PASS

인코딩: 변경 파일 UTF-8 유지 확인
```

### 이번 라운드에서 변경한 파일

- `src/face_age_gender_predictor/camera/camera_detector.py` (Finding 1)
- `src/face_age_gender_predictor/inference/CNNmodel.py` (Finding 2)
- `tests/test_camera_detector.py`, `tests/test_cnnmodel.py` (회귀 테스트)
- `AI-Agents/IMPLEMENTATION.md` (이 섹션)

### 아직 남은 BLOCKED / 미해결 항목

- **Finding 3 (`PR.md`) / Finding 4 (`TASK.md`, `ACCEPTANCE.md`)**: 경계/파괴 위험으로
  Claude가 직접 수정하지 않음 → 사용자/Codex Release 결정 대기.
- **실제 `.pt` 모델 추론 미검증**: 환경에 `models/Best_Age_Estimate_model_traced.pt`
  없음. (REVIEW.md Not Verified와 동일)
- **torch/PyQt5 DLL 충돌**: 위 Risks 항목. 사용자 환경에서 VC++ Redistributable 설치
  후 실제 추론 검증 필요.
- **실제 웹캠 GUI 수동 QA**: 첫 측정/자동 재감지/버튼 재활성화/2차 측정/종료 시 자원
  해제. (수동 QA 영역)

## QA Fix Round 2 (Codex REVIEW NEEDS_FIX 대응 — 측정 얼굴 미리보기 버그)

이전 라운드의 코드 지적(Finding 1·2)은 REVIEW에서 resolved로 확인되었고, 문서
지적(PR.md/TASK.md/ACCEPTANCE.md)은 역할 경계상 QA blocker가 아니라고 명시되었다.
이번 라운드는 사용자 수동 QA에서 발견된 release-blocking GUI 버그 1건만 대응한다.

### Finding — 재측정 시 측정된 얼굴 사진/미리보기가 갱신되지 않음 → 수정함

- 증상: 첫 측정 성공 → 자동 재감지 → 측정 버튼 재활성화 → 사용자가 다시 측정 →
  다음 결과에서 나이/성별 등 값은 정상 표시되지만, 측정된 얼굴 사진 영역이
  비어 있거나(또는 이전 상태로) 갱신되지 않는 경우가 있다.
- 원인: `AgeEstimatorWindow._show_success_result()`가 결과 표시 시점의 **live**
  `self.latest_frame` / `self.latest_face_box`로 미리보기 얼굴을 만들었다. 그런데
  40프레임 캡처가 끝나면 `CameraDetector._record_frames()`가 즉시 감지 루프를 재개해
  ANALYZING 동안 새 미리보기 프레임으로 `latest_frame`/`latest_face_box`를 덮어쓴다.
  결과 도착 시점에 사용자가 얼굴을 움직였거나 감지가 잠시 끊겨 `latest_face_box`가
  `None`이면 `_make_preview_face()`가 `None`을 반환하고, 카운트다운에서 이미 비워둔
  미리보기가 그대로 빈 상태로 남는다. 타이밍 의존이라 "가끔" 발생하며 재측정에서 더 자주
  드러난다.
- 수정: 이번 측정에서 캡처한 얼굴을 **고정 스냅샷**으로 보관해 결과 표시에 사용한다.
  - `AgeEstimatorWindow`에 `captured_frame` / `captured_face_box` 상태 추가.
  - 카운트다운/캡처 상태(`COUNTDOWN`/`COLLECTING`)에서 얼굴 bbox가 있는 마지막
    미리보기 프레임을 스냅샷으로 고정(`on_preview_frame`).
  - 새 측정 시작(COUNTDOWN)에서 이전 스냅샷을 초기화(`on_state_changed`)하여 이전
    측정 사진이 남지 않게 한다.
  - `_show_success_result()`는 live 프레임 대신 고정 스냅샷을 사용한다(스냅샷이 없으면
    live로 폴백). 캡처 종료 후 재개되는 감지 루프가 live 프레임을 덮어써도 결과 얼굴은
    이번 측정에서 캡처한 얼굴로 갱신된다.
- 파일: `src/face_age_gender_predictor/app/main_window.py`
- 범위 메모: GUI 시각 재디자인이 아니라, 재측정 정확성에 필요한 최소 상태/슬롯 변경이다
  (TASK가 허용하는 범위).

### 회귀 테스트

- `tests/test_window_preview.py` (신규): offscreen으로 `AgeEstimatorWindow`를 띄워
  `측정1 성공(사진 표시) → 재감지(사진 유지) → 측정 버튼 재활성화 → 측정2 성공(사진 갱신)`
  흐름을 모사하고, 2차 측정 결과에서 미리보기 사진이 갱신되는지(`preview_face_label`에
  pixmap이 설정되고 placeholder 텍스트가 사라지는지) 검증한다. 캡처 종료 후 감지 루프가
  live 프레임을 얼굴 없음으로 덮어쓰는 상황도 모사한다.
- `tests/conftest.py` (신규): 위젯/QObject 테스트가 한 프로세스에서 공존하도록 세션 단위
  offscreen `QApplication` 픽스처(`qapp`)를 제공.
- `tests/test_controller.py`: 로컬 `QCoreApplication` 픽스처를 공유 `qapp`(QApplication)
  픽스처로 대체(같은 프로세스에서 위젯 테스트와 충돌 방지). 테스트 로직 변경 없음.

스모크로 수정 전 동작(스냅샷 없이 live 프레임 사용)에서는 결과 미리보기 pixmap이
설정되지 않아(blank) 회귀 테스트가 실패함을 확인했고, 수정 후에는 통과한다.

### QA Fix Round 2 테스트 결과

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS — 37 passed in 0.50s

명령: .\.venv\Scripts\python.exe -m py_compile src/face_age_gender_predictor/app/main_window.py
결과: PASS

인코딩: 변경/신규 파일 UTF-8 유지 확인
```

### 이번 라운드에서 변경한 파일

- `src/face_age_gender_predictor/app/main_window.py` (미리보기 스냅샷 수정)
- `tests/test_window_preview.py` (신규 회귀 테스트)
- `tests/conftest.py` (신규 공유 qapp 픽스처)
- `tests/test_controller.py` (공유 qapp 픽스처로 전환)
- `AI-Agents/IMPLEMENTATION.md` (이 섹션)

### 아직 남은 BLOCKED / 미해결 항목

- **(중요) torch/PyQt5 DLL 충돌 — 이 머신 GUI 실제 추론 블로커**: 모델 파일이 존재하는
  지금, 실제 GUI 경로(PyQt5 → InferenceWorker → torch)는 이 머신에서 `WinError 1114`로
  torch 로드에 실패한다(모델 자체는 단독 프로세스에서 정상 로드/추론됨). 사용자 환경에서
  VC++ Redistributable 설치 후 GUI 추론이 되는지 확인 필요. (위 Risks의 import-order
  대안 적용 여부는 사용자 결정)
- **실제 웹캠 GUI 수동 QA 재확인**: 오프스크린 테스트로 미리보기 갱신 경로는 검증했으나,
  실제 웹캠에서 `측정1(사진 표시) → 재감지 → 버튼 재활성화 → 측정2(사진 표시) → 종료 시
  자원 해제`를 사용자가 최종 확인해야 한다.
- **실제 `.pt` 모델 추론 — 검증 완료**: `models/Best_Age_Estimate_model_traced.pt`로
  로드/출력 형태/dict 계약 검증함(위 "Real Model Verification"). 단, mediapipe로 실제
  얼굴을 검출하는 end-to-end는 웹캠 수동 QA 영역.
- **신규 테스트/픽스처 untracked**: `tests/test_cnnmodel.py`, `tests/test_controller.py`,
  `tests/test_window_preview.py`, `tests/conftest.py`는 커밋 시 함께 스테이징 필요
  (커밋은 사용자/Release 담당).

## QA Fix Round 4 (Codex REVIEW NEEDS_FIX 대응 — 나이 확신도 지표)

이번 라운드 REVIEW의 NEEDS_FIX는 1건(나이 확신도 표시)이며 그것만 수정했다.
이전 라운드 지적(재측정 미리보기 버그, 모델 연동, DLL 선로딩)은 REVIEW에서
resolved/accepted로 확인되었고, PR.md/TASK.md/ACCEPTANCE.md는 QA blocker가 아님으로
명시되어 추가 조치하지 않았다.

### Finding — 나이 확신도(age confidence)가 사용자 지표로 오해를 부름 → 수정함

- 증상: GUI가 `max(age_probs) * 100`(26-클래스 중 단일 최댓값)을 "나이 확신도"로
  표시했다. 수학적으로는 단일 나이 클래스 확률이 맞지만 값이 너무 낮게 읽혀 라벨과
  맞지 않았다.
- 수정: 예측 나이를 중심으로 ±2세 윈도우(최대 5개 클래스)의 확률 질량을 합산해
  표시하도록 변경했다. 유효 클래스 범위(15~40세) 밖의 나이는 제외하고, 표시값은
  `min(100.0, max(0.0, total * 100.0))`으로 0~100% clamp한다.
  - 공식: `confidence = sum(P(age-2) .. P(age+2)) * 100`, 중심 = round(predicted_age),
    유효 범위 15..40.
- 구현: `AgeEstimatorWindow._compute_age_confidence(age_probs, predicted_age)`
  classmethod 추가(인스턴스 없이 단위 테스트 가능, 기존 `_expanded_square_face_box`
  스타일과 일치). `_show_success_result()`가 이 메서드를 사용하도록 교체.
- 파일: `src/face_age_gender_predictor/app/main_window.py`
- 범위 메모: 표시 지표 계산만 변경했고 UI 레이아웃/디자인 변경은 없다.

### 회귀/단위 테스트

`tests/test_main_window.py`에 4건 추가:

- `test_age_confidence_uses_plus_minus_two_window`: ±2세(5개 클래스) 윈도우 합을
  사용하고, 단일 클래스 최댓값보다 큰 값임을 확인.
- `test_age_confidence_clamped_to_0_100`: 확률 합이 1.0을 초과해도 100%로 clamp.
- `test_age_confidence_window_clipped_at_age_range_boundary`: 경계(15세)에서 범위 밖
  클래스(13·14세)는 제외하고 합산.
- `test_age_confidence_handles_empty_or_none`: 빈 확률분포/None 예측 나이는 0.0 반환.

### QA Fix Round 4 테스트 결과

```text
명령: .\.venv\Scripts\python.exe -m pytest -q
결과: PASS — 41 passed in 0.26s  (직전 37 + 나이 확신도 4)

명령: .\.venv\Scripts\python.exe -m py_compile src/face_age_gender_predictor/app/main_window.py
결과: PASS

인코딩: 변경 파일 UTF-8 유지 확인
```

### 이번 라운드에서 변경한 파일

- `src/face_age_gender_predictor/app/main_window.py` (나이 확신도 윈도우 계산 + clamp)
- `tests/test_main_window.py` (나이 확신도 단위 테스트 4건)
- `AI-Agents/IMPLEMENTATION.md` (이 섹션)

### 아직 남은 BLOCKED / 미해결 항목

- **실제 웹캠 GUI 수동 QA**: 첫 측정/자동 재감지/버튼 재활성화/2차 측정/종료 시 자원
  해제, 그리고 새 나이 확신도 표시값이 사용자에게 자연스럽게 보이는지 실환경 확인 필요.
- **실제 `.pt` 모델 추론**: 모델 로드/출력 형태/dict 계약은 검증 완료. mediapipe로 실제
  얼굴을 검출하는 end-to-end는 웹캠 수동 QA 영역.
- **신규 테스트/픽스처 untracked**: `tests/conftest.py`, `tests/test_cnnmodel.py`,
  `tests/test_controller.py`, `tests/test_main_window.py`, `tests/test_window_preview.py`는
  커밋 시 함께 스테이징 필요(커밋은 사용자/Release 담당).
- **(권장, blocker 아님)** REVIEW Follow-up: `tests/test_window_preview.py`를 2차 측정에서
  시각적으로 다른 프레임을 쓰도록 강화하면 stale-image 회귀를 더 정밀하게 잡을 수 있다.
