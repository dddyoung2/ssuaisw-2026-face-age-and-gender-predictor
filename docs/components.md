# Components

## `src/face_age_gender_predictor/app/main_app.py`

공식 GUI 앱 진입점이다. `QApplication`, `AgeEstimatorWindow`, `SystemController`를 생성하고 `connect_window_and_controller`로 signal/slot을 연결한다.

주요 책임:

- 앱 실행과 종료
- GUI View와 Controller 연결
- 카메라 시작, 측정 요청, 카메라 종료 요청 연결
- Controller 상태, 프레임, 진행률, 결과, 오류를 GUI 표시 slot에 연결

## `SystemController`

앱 상태 전이를 관리하는 중재자다. 화면을 직접 그리지 않고, 무거운 작업도 직접 수행하지 않는다.

주요 책임:

- 카메라 WorkerThread 생성과 정리
- 얼굴 준비 상태 추적
- 측정 요청 검증
- 카운트다운 시작과 종료 처리
- 캡처 요청 전달
- 추론 WorkerThread 생성과 결과 수신
- 성공/실패/오류 상태를 GUI에 signal로 전달
- 정상 측정 완료 후 재인식 시 측정 버튼 재활성화

## `src/face_age_gender_predictor/app/main_window.py`

PyQt5 GUI View 파일이다. 중심 클래스는 `AgeEstimatorWindow`다.

주요 책임:

- 카메라 미리보기 표시
- 얼굴 bbox와 중앙 guide box 표시
- 상태, 버튼, 카운트다운, 진행률 표시
- 측정 전/중/후 UI 상태 전환
- 얼굴 미리보기 스냅샷, 나이, 성별, 신뢰도, 나이 분포 표시
- 사용자 입력을 signal로 Controller에 전달

주의:

- 공식 앱 흐름에서 카메라 읽기와 모델 추론은 View가 직접 수행하지 않는다.
- GUI 위젯 갱신은 MainThread에서만 수행한다.
- `main_window.py` 단독 실행은 화면 확인 목적이며 전체 시스템 흐름은 `main_app.py`를 사용한다.

## `src/face_age_gender_predictor/app/workers.py`

PyQt Worker 객체를 정의한다.

### `CameraBridgeWorker`

`CameraDetector`를 QThread 환경에서 실행하고, callback 기반 이벤트를 PyQt signal로 변환한다.

주요 signal:

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

주요 slot:

```text
start_camera()
start_capture()
resume_detection()
stop_camera()
```

### `InferenceWorker`

캡처된 프레임을 받아 추론과 후처리를 수행한다.

주요 책임:

- frame list 검증
- `CNNmodel.predict_frames(frames)` 호출
- `result_processor.process_predictions(predictions)` 호출
- 진행률, 결과, 오류 signal 전달

추론은 `InferenceThread`에서 수행되며 GUI MainThread를 막지 않아야 한다.

## `src/face_age_gender_predictor/camera/camera_detector.py`

카메라 장치와 얼굴 감지, 캡처를 담당한다.

주요 책임:

- `cv2.VideoCapture` 소유
- 프레임 읽기
- 얼굴 감지와 bbox 관리
- 얼굴 준비 상태 판단
- 40프레임 캡처
- 캡처 진행률과 완료 callback 호출
- 종료 시 카메라 자원 정리

## `src/face_age_gender_predictor/inference/CNNmodel.py`

얼굴 전처리와 TorchScript 모델 추론을 담당하는 앱용 API 모듈이다.

현재 기준:

- import 시 모델 로드, 샘플 추론, plot 실행을 하지 않는다.
- 기본 모델 경로는 `models/Best_Age_Estimate_model_traced.pt`이다.
- 모델은 필요할 때 lazy load한다.
- 같은 프로세스 안에서는 캐시된 모델을 재사용한다.
- `predict_frames()`는 프레임 list를 받아 prediction dict list를 반환한다.

권장 호출:

```python
from face_age_gender_predictor.inference.CNNmodel import predict_frames
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

## `src/face_age_gender_predictor/processing/result_processor.py`

프레임별 prediction list를 최종 result dict로 집계한다.

주요 책임:

- 유효 prediction 필터링
- 평균 나이 계산
- 평균 gender score 기반 최종 성별 결정
- `age_probs` 평균 계산
- `gender_confidence` 평균 계산
- `valid_count`와 실패 reason 제공

최종 result:

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

개발 보조 스크립트 위치다. 제품 흐름의 기준은 아니다.

용도:

- 카메라 단독 확인
- OpenCV 미리보기 확인
- 로컬 디버깅

## `tests/`

자동 테스트 위치다.

현재 테스트 범위:

- `test_result_processor.py`
- `test_camera_detector.py`
- `test_cnnmodel.py`
- `test_controller.py`
- `test_main_window.py`
- `test_window_preview.py`
- `test_workers.py`

테스트는 모델 파일이 없어도 import 안전성과 오류 경로를 검증할 수 있어야 한다. 실제 모델 파일과 웹캠이 필요한 end-to-end 흐름은 수동 QA로 분리한다.
