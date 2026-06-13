# Architecture

## 전체 흐름

이 프로젝트의 기준 아키텍처는 GUI MainThread와 작업 WorkerThread를 분리하는 구조다.

```text
PyQt5 GUI
→ SystemController
→ CameraBridgeWorker / CameraDetector
→ InferenceWorker / CNNmodel
→ result_processor
→ SystemController
→ PyQt5 GUI
```

GUI는 사용자의 입력과 결과 표시를 담당하고, 카메라와 추론처럼 시간이 오래 걸리거나 blocking 가능성이 있는 작업은 WorkerThread에서 실행한다.

## 패키지 구조

```text
src/face_age_gender_predictor/
├─ app/
│  ├─ main_app.py
│  ├─ main_window.py
│  └─ workers.py
├─ camera/
│  └─ camera_detector.py
├─ inference/
│  └─ CNNmodel.py
└─ processing/
   └─ result_processor.py
```

## 런타임 구성

목표 런타임 구성:

```text
MainThread
├─ AgeEstimatorWindow / MainWindow
└─ SystemController

CameraThread
└─ CameraBridgeWorker
   └─ CameraDetector

InferenceThread
└─ InferenceWorker
   └─ CNNmodel.predict_frames / TorchScript model

Processing
└─ result_processor.process_predictions
```

GUI 통합 후 현재 `main_window.py`의 런타임 구성(위 목표 구성과 일치):

```text
MainThread
└─ AgeEstimatorWindow (View)
   ├─ 버튼 입력 → start_camera/measurement/stop/close signal
   └─ SystemController signal 수신 → 위젯 갱신(미리보기 overlay, 상태, 결과)
```

초기 업로드본의 `cv2.VideoCapture`, 다수 `QTimer`(frame/countdown/collection/analysis),
Haar cascade, 임시 heuristic 예측은 통합 과정에서 GUI 클래스 밖으로 제거되었고, 카메라와 추론
책임은 CameraThread/InferenceThread로 분리되었다.

원칙:

- MainWindow는 MainThread에서만 위젯을 갱신한다.
- CameraDetector는 카메라 장치를 하나의 경로에서만 소유한다.
- InferenceWorker는 분석 요청마다 독립적으로 실행하고 완료 후 정리한다.
- result_processor는 카메라, GUI, 모델 파일 경로에 의존하지 않는다.

## 데이터 흐름

목표 데이터 흐름:

```text
camera frame
→ face detection state
→ GUI ready state
→ measurement request
→ countdown
→ capture request
→ frames: list[np.ndarray]
→ predictions: list[dict]  # CNNmodel 출력
→ result: dict
→ GUI result view
```

이번 병합 범위에서는 `InferenceWorker`가 임시 prediction 대신 `CNNmodel.predict_frames`를
호출해 `models/Best_Age_Estimate_model_traced.pt` 기반 TorchScript 추론 결과를
`result_processor`로 전달한다. 모델 파일 로드 실패, 전처리 실패, 추론 실패는 앱 크래시가
아니라 GUI 오류 또는 실패 result 흐름으로 전달한다.

GUI 통합 후 현재 데이터 흐름(위 목표 흐름과 일치):

```text
AgeEstimatorWindow 버튼 클릭
→ SystemController 요청 signal
→ CameraBridgeWorker(CameraThread) / CameraDetector: 프레임 읽기·얼굴 감지·40프레임 캡처
→ frames_ready → SystemController
→ InferenceWorker(InferenceThread): predictions 생성 → result_processor
→ result_ready → SystemController
→ AgeEstimatorWindow: 미리보기 overlay, 상태/결과/히스토그램 갱신
```

초기 업로드본에서 GUI가 직접 소유하던 `cv2.VideoCapture`, 얼굴 감지, frame collection,
임시 prediction은 통합 과정에서 카메라/추론 Worker 및 `CNNmodel.py` 경로로 분리한다.

prediction dict 형식:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```

result dict 목표 형식:

```python
{
    "success": bool,
    "age": float | None,
    "gender": int | None,
    "age_probs": list[float] | None,
    "gender_confidence": float | None,
    "valid_count": int,
    "reason": str | None,
}
```

## 상태 전이

목표 상태 전이:

```text
IDLE
→ COUNTDOWN
→ CAPTURING
→ ANALYZING
→ DONE
→ IDLE
```

실패 흐름:

```text
COUNTDOWN / CAPTURING / ANALYZING
→ ERROR
→ IDLE
```

상태별 책임:

- `IDLE`: 얼굴 감지 상태를 받고 측정 가능 여부를 표시한다.
- `COUNTDOWN`: 측정 버튼을 잠그고 카운트다운을 표시한다.
- `CAPTURING`: 40프레임 캡처 진행 상태를 표시한다.
- `ANALYZING`: 모델 추론과 후처리 진행 상태를 표시한다.
- `DONE`: 최종 결과를 표시하고 재측정을 준비한다.
- `ERROR`: 실패 원인을 표시하고 복구 가능한 상태로 돌아간다.

현재 GUI 표시 상태:

```text
IDLE
→ READY
→ COUNTDOWN
→ COLLECTING
→ ANALYZING
→ DONE 또는 ERROR
```

`SystemController`의 `IDLE`은 얼굴 준비 여부에 따라 GUI에서 `IDLE` 또는 `READY`로 표시된다.
`SystemController`의 `CAPTURING`은 GUI에서 `COLLECTING`으로 표시된다.

## Signal 설계

GUI에서 SystemController로:

```text
start_camera_requested
measurement_requested
stop_camera_requested
close_requested
```

SystemController에서 GUI로:

```text
status_changed(message)
state_changed(state_name)
face_ready_changed(bool)
camera_running_changed(bool)
measure_button_enabled_changed(bool)
countdown_changed(value)
capture_progress_changed(current, total)
inference_progress_changed(current, total)
preview_frame_changed(payload)
result_ready(result)
error_occurred(message)
```

SystemController에서 CameraWorker로:

```text
start_capture_requested
resume_detection_requested
stop_camera_requested
```

CameraWorker에서 SystemController로:

```text
started()
status_changed(str)
face_ready_changed(bool)
preview_frame_ready(object)
capture_progress(int, int)
frames_ready(object)
error_occurred(str)
finished()
```

InferenceWorker에서 SystemController로:

```text
progress_changed(int, int)
result_ready(dict)
error_occurred(str)
finished()
```

현재 통합된 `main_app.py`는 `connect_window_and_controller`에서 GUI 요청 signal을
`SystemController` slot에 연결하고, controller 상태/결과 signal을 GUI 표시 slot에 연결한다.
업로드 초기 상태의 `main_window.py`처럼 GUI가 카메라와 분석 타이머를 직접 소유하는 구조는
최종 기준이 아니다.

GUI 통합 시 우선 연결할 이벤트:

```text
start_camera_button.clicked
→ SystemController 또는 CameraWorker start 요청

measure_button.clicked
→ SystemController measurement_requested

stop_button.clicked / closeEvent
→ SystemController shutdown 또는 stop_camera 요청
```

## 실패와 방어 지점

반드시 다뤄야 할 실패 지점:

- 카메라 장치를 열 수 없음
- 얼굴이 감지되지 않음
- 카운트다운 중 얼굴이 사라짐
- 촬영 시작 직전 bbox가 유효하지 않음
- 40프레임 캡처 중 프레임 읽기 실패
- 모델 파일이 없음
- 전처리에서 얼굴 crop 실패
- 유효 prediction 수가 30개 미만
- WorkerThread가 중복 실행됨
- 창 종료 시 카메라 또는 스레드가 남아 있음

특히 카운트다운이 끝난 뒤 얼굴 상태를 다시 확인해야 한다. 준비 완료 상태가 과거 프레임 기준으로 남아 있으면, 사용자가 화면에서 사라진 뒤에도 촬영이 진행될 수 있다.

## 모듈 의존 방향

권장 의존 방향:

```text
GUI
→ app/SystemController
→ app/workers
→ camera / inference
→ processing
```

피해야 할 의존:

- `processing`이 GUI나 카메라에 의존
- `camera`가 GUI 위젯을 직접 수정
- `inference`가 MainWindow를 직접 호출
- `CNNmodel.py` import만으로 모델 로드와 샘플 추론 실행

## QA 관점의 아키텍처 기준

GUI 통합은 다음 조건을 만족해야 한다.

- GUI가 멈추지 않는다.
- 카메라 프레임이 계속 갱신된다.
- 측정 중 버튼 중복 클릭이 막힌다.
- 추론 중 UI가 응답 가능하다.
- 성공/실패 후 재측정할 수 있다.
- 종료 시 카메라와 QThread가 정리된다.
- 오류는 콘솔에만 남지 않고 GUI에도 표시된다.
