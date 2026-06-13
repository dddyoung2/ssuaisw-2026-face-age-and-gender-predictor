# Architecture

## 전체 흐름

이 프로젝트의 구조는 GUI MainThread와 작업 WorkerThread를 분리하는 방식이다.

```text
PyQt5 GUI
-> SystemController
-> CameraBridgeWorker / CameraDetector
-> InferenceWorker / CNNmodel
-> result_processor
-> SystemController
-> PyQt5 GUI
```

GUI는 사용자 입력과 결과 표시를 담당한다. 카메라 읽기, 얼굴 감지, 40프레임 캡처, 모델 추론처럼 시간이 걸리거나 blocking 가능성이 있는 작업은 WorkerThread에서 실행한다.

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

## 스레드 구성

```text
MainThread
├─ AgeEstimatorWindow
└─ SystemController

CameraThread
└─ CameraBridgeWorker
   └─ CameraDetector

InferenceThread
└─ InferenceWorker
   ├─ CNNmodel.predict_frames
   └─ result_processor.process_predictions
```

원칙:

- GUI 위젯 갱신은 MainThread에서만 수행한다.
- `CameraDetector`는 카메라 장치를 하나의 경로에서만 소유한다.
- `InferenceWorker`는 분석 요청마다 독립적으로 실행되고 완료 후 정리된다.
- `result_processor`는 GUI, 카메라, 모델 파일 경로에 의존하지 않는다.
- `CNNmodel.py`는 import만으로 모델을 로드하거나 추론하지 않는다.

## 데이터 흐름

```text
camera frame
-> face detection state
-> GUI ready state
-> measurement request
-> countdown
-> capture request
-> frames: list[np.ndarray]
-> predictions: list[dict]
-> result: dict
-> GUI result view
```

prediction dict:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```

result dict:

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

Controller 기준 상태:

```text
IDLE
-> COUNTDOWN
-> CAPTURING
-> ANALYZING
-> DONE
-> IDLE 또는 READY
```

실패 흐름:

```text
COUNTDOWN / CAPTURING / ANALYZING
-> ERROR
-> IDLE 또는 READY
```

GUI 표시 상태는 View 표현을 위해 `READY`, `COLLECTING` 같은 이름을 사용할 수 있다. 핵심은 사용자가 측정 가능한 상태인지, 측정 중인지, 결과 표시 중인지가 일관되게 전달되는 것이다.

반복 측정 정책:

- `DONE` 상태에서는 결과 표시를 유지한다.
- 얼굴이 다시 정상 인식되면 측정 버튼을 다시 활성화한다.
- 사용자가 다시 측정 시작을 누르는 순간 이전 결과 표시를 초기화하고 새 측정 흐름으로 들어간다.

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

## 실패와 방어 지점

반드시 다뤄야 하는 실패 지점:

- 카메라 장치를 열 수 없음
- 얼굴이 감지되지 않음
- 카운트다운 중 얼굴이 사라짐
- 캡처 시작 직전 bbox가 유효하지 않음
- 40프레임 캡처 중 프레임 읽기 실패
- 모델 파일 없음
- 모델 로드 실패
- 전처리 중 얼굴 crop 실패
- 유효 prediction 수가 30개 미만
- WorkerThread 중복 실행 요청
- 창 종료 후 카메라나 스레드가 남아 있음

카운트다운이 끝난 뒤에는 얼굴 상태를 다시 확인해야 한다. 준비 완료 상태가 과거 프레임 기준으로 남아 있으면 사용자가 화면에서 벗어난 뒤에도 캡처가 진행될 수 있다.

## 의존 방향

권장 의존 방향:

```text
GUI
-> app/SystemController
-> app/workers
-> camera / inference
-> processing
```

피해야 할 의존:

- `processing`이 GUI나 카메라에 의존
- `camera`가 GUI 위젯을 직접 수정
- `inference`가 MainWindow를 직접 호출
- `CNNmodel.py` import만으로 모델 로드나 샘플 추론 실행

## QA 관점의 구조 기준

- GUI가 멈추지 않는다.
- 카메라 프레임이 계속 갱신된다.
- 측정 중 버튼 중복 클릭이 막힌다.
- 추론 중 UI가 응답 가능하다.
- 성공/실패 후 재측정할 수 있다.
- 종료 시 카메라와 QThread가 정리된다.
- 오류가 콘솔에만 남지 않고 GUI에도 표시된다.
