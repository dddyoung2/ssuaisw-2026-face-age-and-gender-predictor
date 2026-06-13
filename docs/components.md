# Components

## `src/face_age_gender_predictor/app/main_window.py`

PyQt5 GUI 화면 계층(View) 파일이다. 현재 중심 클래스는 `AgeEstimatorWindow`이며, 정식 실행은 `main_app.py`가 `SystemController`와 연결해서 수행한다.

현재 GUI 책임:

- 카메라 미리보기 표시
- 중앙 guide box와 얼굴 감지 bbox 표시
- 현재 상태와 얼굴 감지 상태 표시
- 카메라 시작, 측정 시작, 카메라 종료 버튼 제공
- 카운트다운 표시
- 40프레임 캡처 진행률 표시
- 측정된 얼굴 preview 표시
- 나이, 성별, 나이 확신도, 성별 확신도 표시
- 15~40세 나이 히스토그램 표시
- 카메라 오류와 얼굴 미감지 안내 메시지 표시
- 버튼/종료 이벤트를 signal로 `SystemController`에 전달
- `SystemController`가 보내는 상태/프레임/진행률/결과/오류 signal을 화면에 표시

현재 포함된 UI 보조 컴포넌트:

- `AspectRatioLabel`: 카메라 프레임을 비율 유지 상태로 표시하는 QLabel
- `MetricCard`: 상태와 얼굴 감지 여부를 카드 형태로 표시
- `AgeHistogramWidget`: 나이 분포 막대 그래프를 직접 paint하는 QWidget
- `AppState`: `IDLE`, `READY`, `COUNTDOWN`, `COLLECTING`, `ANALYZING`, `DONE`, `ERROR`
- `StateMeta`: 상태별 라벨, 배너, 안내 문구, 색상 정의

현재 구현상 주의:

- `AgeEstimatorWindow`는 `cv2.VideoCapture`를 직접 소유하지 않는다.
- GUI는 카메라 읽기, 얼굴 감지, 40프레임 캡처, 모델 추론을 직접 수행하지 않는다.
- GUI 위젯 갱신은 MainThread에서만 수행한다.
- 단독 실행(`python -m face_age_gender_predictor.app.main_window`)은 가능하지만, 이 경우 `SystemController`가 없으므로 카메라/추론 없이 안내용 창만 뜬다.

통합 기준:

- `AgeEstimatorWindow`는 화면 표시와 사용자 입력만 담당한다.
- 카메라 읽기와 40프레임 캡처는 `CameraBridgeWorker`/`CameraDetector` 경로에서 수행한다.
- 추론 WorkerThread는 `CNNmodel.predict_frames()`를 호출해 `models/Best_Age_Estimate_model_traced.pt` 기반 prediction을 생성하고 `result_processor`로 전달한다.
- GUI와 `SystemController`는 `connect_window_and_controller`에서 signal/slot으로 연결한다.

권장 import:

```python
from face_age_gender_predictor.app.main_window import AgeEstimatorWindow
```

나중에 이름을 더 일반화하려면 `AgeEstimatorWindow`를 `MainWindow`로 alias하거나 클래스명을 바꿀 수 있다. 단, 현재 업로드된 코드의 실제 클래스명은 `AgeEstimatorWindow`다.

## `src/face_age_gender_predictor/app/main_app.py`

GUI 앱의 실행 진입점과 시스템 상태 제어를 담당한다.

현재 `main_app.py`는 `QApplication`, `SystemController`, `AgeEstimatorWindow`를 생성하고 `connect_window_and_controller`로 GUI와 controller를 연결하는 정식 GUI 진입점이다.

### `AppState`

프로그램 상태를 나타낸다.

```text
IDLE
COUNTDOWN
CAPTURING
ANALYZING
DONE
ERROR
```

### `SystemController`

전체 흐름의 중재자다.

책임:

- GUI 요청 수신
- 얼굴 준비 상태 관리
- 측정 요청 검증
- 카운트다운 시작과 종료 처리
- 촬영 요청 signal 발행
- frames 수신 후 InferenceWorker 실행
- 추론 결과를 GUI에 전달
- 오류 상태와 복구 흐름 관리
- 종료 시 카메라와 스레드 정리

SystemController는 화면을 직접 그리지 않고, 무거운 작업도 직접 수행하지 않는다. GUI 통합 후에는 `AgeEstimatorWindow`의 버튼 이벤트와 SystemController의 measurement/camera 요청 signal을 연결하는 중재 계층이 필요하다.

## `src/face_age_gender_predictor/app/workers.py`

PyQt Worker 객체들을 정의한다.

### `CameraBridgeWorker`

`CameraDetector`를 PyQt signal/slot 구조로 감싼다.

주요 signal:

- `started()`
- `status_changed(str)`
- `face_ready_changed(bool)`
- `preview_frame_ready(object)`
- `capture_progress(int, int)`
- `frames_ready(object)`
- `error_occurred(str)`
- `finished()`

주요 slot:

- `start_camera()`
- `start_capture()`
- `resume_detection()`
- `stop_camera()`

GUI 통합 시 CameraBridgeWorker는 CameraThread에서 실행되어야 한다.

### `InferenceWorker`

40프레임을 받아 추론 WorkerThread에서 prediction 생성과 후처리 흐름을 수행한다.

현재 책임:

- 전달받은 frame 리스트 검증
- `CNNmodel.predict_frames(frames)` 호출
- prediction dict 리스트 생성
- `result_processor.process_predictions` 호출
- 진행률, 결과, 오류 signal 전달

이번 병합 범위에서는 fake prediction 흐름을 제거하고 실제 앱용 모델 추론 API로 교체한다.
모델 파일 없음, 모델 로드 실패, 전처리 실패, 추론 실패는 `error_occurred` 또는 실패 result로 전달한다.

### `ConsoleCommandWorker`

개발 초기 단계의 보조 입력 Worker다. 최종 GUI 앱의 기본 흐름에서는 사용하지 않는다. 필요하다면 개발자 디버그 옵션으로만 남긴다.

## `src/face_age_gender_predictor/camera/camera_detector.py`

카메라 장치와 얼굴 감지, 40프레임 캡처를 담당한다.

책임:

- `cv2.VideoCapture` 소유
- 프레임 읽기
- 얼굴 감지
- 최신 프레임과 얼굴 bbox 저장
- 얼굴 준비 상태 안정화
- 캡처 요청 시 40프레임 수집
- 캡처 완료 callback 호출

GUI 통합 시 중요한 보강점:

- 카운트다운 종료 또는 촬영 시작 직전에 최신 얼굴 상태를 재검증한다.
- 얼굴이 사라졌거나 bbox가 유효하지 않으면 캡처를 시작하지 않는다.
- 종료 시 카메라 자원과 OpenCV 창 자원을 정리한다.

## `src/face_age_gender_predictor/inference/CNNmodel.py`

얼굴 전처리와 TorchScript 모델 추론을 담당할 모듈이다.

현재 포함된 요소:

- MediaPipe 0.10.21 기반 얼굴 검출과 정렬
- `FacePreprocessor`
- `AFADPreprocessor`
- TorchScript 모델 로드 실험 코드
- 단일 이미지 추론과 그래프 시각화 예제

GUI 앱 연결 전에 필요한 정리:

- import 시 모델 로드와 샘플 추론이 자동 실행되지 않게 한다.
- 앱용 API를 제공한다.

권장 API:

```python
def predict_frames(frames: list) -> list[dict]:
    ...
```

반환 prediction dict:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```

## `src/face_age_gender_predictor/processing/result_processor.py`

프레임별 prediction 리스트를 최종 결과로 집계한다.

현재 책임:

- 평균 나이 계산
- 평균 gender 원시값 기준 최종 성별 결정
- `age_probs` 원소별 평균 계산
- `gender_confidence` 평균 계산

목표 책임:

- 유효 prediction 필터링
- `valid_count` 계산
- `valid_count >= 30`이면 성공
- `valid_count < 30`이면 실패
- GUI가 표시하기 쉬운 result dict 반환

권장 최종 result:

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

## `scripts/`

개발자 보조 스크립트 위치다.

용도:

- 카메라 단독 확인
- OpenCV 미리보기 확인
- GUI와 무관한 빠른 디버깅

스크립트 동작이 GUI 앱의 기준이 되면 안 된다.

## `tests/`

자동 테스트 위치다.

현재는 `result_processor` 테스트가 중심이며, GUI 통합 후에는 Worker와 상태 전이 테스트를 보강해야 한다.
