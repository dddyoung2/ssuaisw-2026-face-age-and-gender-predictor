# SPEC

## 목적

이 문서는 GUI 기반 실시간 나이/성별 예측 앱의 기능 명세와 QA 기준을 정의한다. 다음 작업자가 `TASK.md`만 보고도 프로젝트 방향을 잃지 않도록, 구현과 검증의 기준점을 제공한다.

## 버전 범위

이번 버전의 목표는 다음 세 가지다.

1. 업로드된 `main_window.py` GUI 코드를 현재 시스템에 부착한다.
2. GUI, 카메라, 추론, 후처리 코드가 QThread 기반으로 안정적으로 분리되어 동작하게 한다.
3. `models/Best_Age_Estimate_model_traced.pt` TorchScript 모델을 InferenceWorker 추론 경로에 연결한다.
4. 정상 작동 여부를 QA 테스트한다.

## 현재 업로드된 GUI 기준

업로드된 GUI 파일:

```text
src/face_age_gender_predictor/app/main_window.py
```

현재 GUI 클래스:

```python
AgeEstimatorWindow
```

현재 GUI가 제공하는 기능:

- PyQt5 `QMainWindow` 기반 창
- Live Camera 영역
- 상태 태그와 안내 문구
- 카메라 시작, 측정 시작, 카메라 종료 버튼
- 얼굴 감지 bbox와 중앙 guide box 표시
- 3초 카운트다운
- 40프레임 RGB 224x224 얼굴 샘플 수집
- 수집 진행률 progress bar
- 측정된 얼굴 preview
- 나이/성별/확신도 표시
- 15~40세 나이 히스토그램
- 카메라 열기 실패, 얼굴 없음 같은 사용자 안내 메시지
- 창 종료 시 카메라 release

현재 GUI의 임시 구현:

- `AgeEstimatorWindow`가 `cv2.VideoCapture`를 직접 소유한다.
- `QTimer`로 frame update, countdown, collection, analysis를 직접 관리한다.
- 실제 CNN 모델이 아니라 임시 heuristic 함수로 나이/성별을 추정한다.
- 기존 `CameraDetector`, `CameraBridgeWorker`, `InferenceWorker`, `result_processor`와 아직 연결되지 않았다.

이번 통합의 목표는 위 GUI를 화면 계층으로 유지하면서 카메라, 수집, 추론, 후처리 책임을 기존 프로젝트 구조로 옮기는 것이다.

## 기능 요구사항

### S1. GUI 실행

- 앱 실행 시 PyQt5 GUI 창이 열린다.
- GUI는 카메라 미리보기 영역, 상태 표시, 측정 버튼, 카운트다운/진행률 영역, 결과 영역을 가진다.
- GUI 창을 닫으면 카메라와 QThread가 정리된다.
- GUI 클래스명은 현재 `AgeEstimatorWindow`이며, 필요 시 `MainWindow`로 정리할 수 있다.

### S2. 카메라 미리보기와 얼굴 준비 상태

- 앱은 카메라 프레임을 지속적으로 읽는다.
- 얼굴이 안정적으로 감지되면 GUI에 준비 완료 상태를 표시한다.
- 얼굴이 감지되지 않으면 측정 버튼을 비활성화하거나 측정 불가 상태를 표시한다.
- 여러 얼굴이 감지되는 경우 우선은 가장 큰 bbox를 기준 후보로 삼는다.

### S3. 측정 요청과 카운트다운

- 사용자는 GUI 측정 버튼으로 측정을 시작한다.
- 측정 시작 후 버튼은 중복 클릭을 막기 위해 비활성화된다.
- 카운트다운은 GUI에 표시된다.
- 카운트다운 종료 시점에 얼굴 상태를 다시 확인한다.
- 얼굴이 사라졌거나 bbox가 유효하지 않으면 촬영을 시작하지 않고 실패 메시지를 표시한다.

### S4. 40프레임 캡처

- 촬영 조건이 만족되면 카메라 워커가 40프레임을 메모리 list로 수집한다.
- 프레임 저장은 파일 저장이 아니라 메모리 전달을 기본으로 한다.
- 캡처 완료 후 `frames_ready(frames)` 흐름으로 SystemController에 전달한다.
- 현재 `main_window.py`는 GUI 내부에서 RGB 224x224 얼굴 crop 샘플을 수집하므로, 통합 시 이 책임을 카메라/전처리/추론 경계에 맞게 재배치해야 한다.

### S5. 모델 추론

- InferenceWorker는 40프레임을 받아 전처리와 모델 추론을 수행한다.
- 모델 추론은 GUI MainThread에서 실행하지 않는다.
- 기본 모델 경로는 `models/Best_Age_Estimate_model_traced.pt`다.
- 모델 파일 없음, 모델 로드 실패, 전처리 실패, 추론 실패는 앱 크래시가 아니라 GUI 오류 또는 실패 result로 전달한다.
- 앱용 추론 API는 다음 형태를 목표로 한다.

```python
def predict_frames(frames: list) -> list[dict]:
    ...
```

prediction dict 형식:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```

현재 `main_window.py`의 `predict_age_from_sample`, `predict_gender_score_from_sample`은 실제 CNN 추론이 아니라 임시 추정 로직이다. 최종 구현에서는 이 로직을 `CNNmodel.py`의 실제 모델 호출로 교체한다.

### S6. 결과 후처리

- `result_processor`는 prediction 리스트를 최종 result dict로 집계한다.
- 유효 prediction이 30개 이상이면 성공이다.
- 유효 prediction이 30개 미만이면 실패다.

성공 result:

```python
{
    "success": True,
    "age": 24.6,
    "gender": 1,
    "age_probs": [...],
    "gender_confidence": 0.91,
    "valid_count": 35,
    "reason": None,
}
```

실패 result:

```python
{
    "success": False,
    "age": None,
    "gender": None,
    "age_probs": None,
    "gender_confidence": None,
    "valid_count": 27,
    "reason": "valid_count_below_30",
}
```

### S7. 결과 표시

- 성공 시 GUI는 나이, 성별, 성별 확신도를 표시한다.
- 실패 시 GUI는 사용자가 이해할 수 있는 실패 메시지를 표시한다.
- 성공/실패 후 측정 버튼은 재시도 가능한 상태로 돌아간다.

## 비기능 요구사항

- GUI는 카메라/추론 중에도 멈추지 않아야 한다.
- Worker는 GUI 위젯을 직접 수정하지 않는다.
- 카메라 자원은 하나의 Worker 경로에서만 소유한다.
- 모델 파일과 개인 이미지는 Git에 포함하지 않는다.
- 오류는 콘솔뿐 아니라 GUI에도 표시한다.

## QA 시나리오

- 정상 흐름: 얼굴 감지, 측정, 카운트다운, 캡처, 추론, 결과 표시
- 얼굴 없음: 측정 버튼 비활성화 또는 측정 거부
- 카운트다운 중 얼굴 사라짐: 촬영 중단과 오류 표시
- 모델 파일 없음: 추론 실패 메시지 표시
- 유효 prediction 30개 미만: 실패 result 표시
- 중복 클릭: 측정 중 추가 요청 무시
- 종료: 카메라와 QThread 정상 정리

## 이번 버전에서 하지 않을 것

- 모델 재학습
- 데이터셋 수집 또는 라벨링
- 대규모 UI 리디자인
- 웹 배포
- 모델 성능 최적화 실험
