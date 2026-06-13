# Development Guide

## 사전 준비

이 프로젝트는 Python 3.10 이상을 기준으로 한다. 주요 의존성은 PyQt5, OpenCV, NumPy, PyTorch, TorchVision, MediaPipe 0.10.21, pytest이며 `pyproject.toml`에서 관리한다.

GUI와 카메라를 확인하려면 다음 환경이 필요하다.

- Windows 또는 PyQt5 GUI 창을 띄울 수 있는 데스크톱 환경
- 웹캠 또는 노트북 내장 카메라
- `models/` 아래 TorchScript `.pt` 모델 파일

## 설치

프로젝트 루트에서 가상환경을 만들고 editable 모드로 설치한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Windows CMD에서는 다음처럼 활성화한다.

```cmd
.venv\Scripts\activate
```

## 모델 파일

실제 추론에는 TorchScript `.pt` 모델이 필요하다. 모델 파일은 Git에 커밋하지 않으며 `models/` 아래에 둔다.

권장 경로:

```text
models/Best_Age_Estimate_model_traced.pt
```

이번 병합 범위에서는 `InferenceWorker`가 `CNNmodel.py`의 앱용 추론 API를 통해 `models/Best_Age_Estimate_model_traced.pt`를 사용하는 실제 TorchScript 추론 경로로 연결되어야 한다. 모델 파일 없음, 전처리 실패, 추론 실패는 GUI 오류 메시지 또는 실패 result로 표시해야 한다.

## 실행

GUI 통합 후 기본 실행 진입점은 PyQt5 GUI 앱이어야 한다.

권장 실행 형태:

```powershell
python -m face_age_gender_predictor.app.main_app
```

현재 업로드된 GUI 프로토타입은 다음 명령으로 단독 실행할 수 있다.

```powershell
python -m face_age_gender_predictor.app.main_window
```

GUI 통합이 완료되어, 이제 `main_window.py`의 `AgeEstimatorWindow`는 화면 표시/버튼 입력만 담당하는 View다. 버튼 입력은 signal로 `SystemController`에 전달되고, 카메라 읽기·40프레임 캡처는 `CameraBridgeWorker`/`CameraDetector`(CameraThread), 추론은 `InferenceWorker`(InferenceThread), 집계는 `result_processor`에서 수행된다. (`main_window.py` 단독 실행은 SystemController가 없어 빈 창만 뜬다.)

따라서 최종 GUI 진입점은 `python -m face_age_gender_predictor.app.main_app` 명령이며, 사용자가 GUI 버튼으로 전체 흐름을 실행한다.

수동 디버깅용 스크립트는 `scripts/` 아래에 둘 수 있다. 단, 이 스크립트들은 제품 흐름의 기준이 아니라 카메라와 후처리를 빠르게 확인하기 위한 개발 보조 도구다.

## 테스트

자동 테스트는 pytest를 사용한다.

```powershell
python -m pytest
```

자동화 테스트는 `result_processor`의 성공/실패 정책, CameraDetector의 캡처 방어 지점, Worker의 모델 API 호출/result 전달 흐름을 중심으로 확인한다. GUI 화면 자체와 실제 웹캠 흐름은 수동 QA 또는 Qt 테스트 도구로 분리한다.

- result_processor 성공/실패 정책 테스트
- InferenceWorker가 prediction 결과를 SystemController에 전달하는 테스트
- 얼굴 없음, 캡처 실패, 종료 같은 오류 흐름 테스트
- 실제 모델 파일 없음/전처리 실패/추론 실패 테스트
- GUI 표시 자체는 수동 QA 또는 Qt 테스트 도구로 분리

## 수동 QA

GUI 통합 후 최소 수동 QA 항목은 다음과 같다.

```text
1. 앱 실행 시 GUI 창이 열린다.
2. 카메라 미리보기가 표시된다.
3. 얼굴이 감지되면 준비 완료 상태와 측정 버튼 활성화가 표시된다.
4. 측정 버튼 클릭 시 버튼이 비활성화되고 카운트다운이 표시된다.
5. 카운트다운 종료 후 40프레임 캡처가 진행된다.
6. 분석 진행률 또는 분석 중 상태가 표시된다.
7. 정상 추론 시 나이/성별/확신도가 표시된다.
8. 얼굴이 사라진 경우 촬영 또는 분석이 중단되고 실패 메시지가 표시된다.
9. 추론 실패 시 사용자에게 오류가 표시된다.
10. 모델 파일 없음 오류도 사용자에게 표시된다.
11. 성공/실패 후 다시 측정할 수 있다.
12. 창 닫기 또는 종료 시 카메라와 스레드가 정리된다.
```

## 개발 주의사항

- GUI MainThread에서 `cv2.VideoCapture.read()`를 반복 호출하지 않는다.
- 카메라 루프와 모델 추론은 WorkerThread에서 실행한다.
- Worker는 GUI 위젯을 직접 수정하지 않고 signal로 상태, 결과, 오류를 전달한다.
- SystemController는 상태 전이와 signal 중계를 담당한다.
- GUI는 화면 표시, 버튼 입력, 사용자 메시지 표시를 담당한다.
- prediction dict 형식은 `result_processor.py`와 반드시 맞춘다.
- 이번 병합 작업은 `CNNmodel.py` 실제 호출을 포함한다.
- `CNNmodel.py`는 앱에서 import해도 샘플 추론이 자동 실행되지 않도록 정리해야 한다.
- 모델 파일, 개인 이미지, 대용량 산출물은 Git에 포함하지 않는다.
- 현재 `main_window.py`는 View 역할로 축소되어야 하며, 카메라와 추론 책임은 WorkerThread 경로에서 처리한다.

권장 prediction 형식:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```
