# Development Guide

## 사전 준비

이 프로젝트는 Python 3.10 이상을 기준으로 한다. 주요 의존성은 PyQt5, OpenCV, NumPy, PyTorch, TorchVision, MediaPipe, pytest이며 `pyproject.toml`에서 관리한다.

GUI와 카메라를 확인하려면 다음 환경이 필요하다.

- PyQt5 GUI 창을 띄울 수 있는 데스크톱 환경
- 웹캠 또는 노트북 내장 카메라
- 실제 추론용 `models/Best_Age_Estimate_model_traced.pt`

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

실제 추론에는 TorchScript `.pt` 모델이 필요하다. 모델 파일은 Git에 커밋하지 않고 `models/` 아래에 둔다.

권장 경로:

```text
models/Best_Age_Estimate_model_traced.pt
```

`CNNmodel.py`는 이 경로를 기본값으로 사용한다. 파일이 없거나 로드에 실패하면 앱은 크래시가 아니라 오류 result 또는 GUI 오류 메시지로 처리해야 한다.

## 실행

공식 GUI 진입점:

```powershell
python -m face_age_gender_predictor.app.main_app
```

`main_window.py`는 View 확인용 단독 실행이 가능하지만, 전체 카메라/추론 흐름은 `main_app.py`에서 `SystemController`와 연결될 때 동작한다.

## 테스트

자동 테스트는 pytest를 사용한다.

```powershell
python -m pytest
```

현재 자동 테스트는 다음 영역을 확인한다.

- 결과 후처리 성공/실패 계약
- CameraDetector 캡처와 상태 흐름
- CNNmodel import 안전성, 모델 경로, 추론 API 계약
- Worker와 Controller의 signal/result 전달
- GUI 표시 보조 로직과 얼굴 미리보기 스냅샷

모델 파일을 사용하는 smoke 확인은 로컬 모델 파일이 있을 때만 수행한다. 웹캠을 쓰는 실제 GUI end-to-end 흐름은 수동 QA로 검증한다.

## 수동 QA 체크리스트

```text
1. 앱 실행 후 GUI 창이 열린다.
2. 카메라 시작 버튼을 누르면 미리보기가 표시된다.
3. 얼굴이 정상 감지되면 준비 완료 상태와 측정 버튼 활성화가 표시된다.
4. 얼굴을 약간 움직여도 즉시 측정 가능 상태가 취소되지 않는다.
5. 얼굴이 사라지면 측정 버튼이 비활성화되거나 측정이 거부된다.
6. 측정 시작 후 버튼이 잠기고 카운트다운이 표시된다.
7. 카운트다운 종료 후 40프레임 캡처 진행률이 표시된다.
8. 분석 중 상태가 표시되고 GUI가 멈추지 않는다.
9. 정상 추론 후 얼굴 미리보기, 나이, 성별, 신뢰도, 나이 분포가 표시된다.
10. 정상 측정 완료 후 결과 화면은 유지된다.
11. 얼굴이 다시 정상 인식되면 측정 시작 버튼이 다시 활성화된다.
12. 재활성화된 측정 시작 버튼을 누르면 이전 결과가 초기화되고 새 측정이 시작된다.
13. 모델 파일이 없을 때 사용자에게 오류가 표시된다.
14. 창 닫기 또는 카메라 종료 시 카메라와 QThread가 정리된다.
```

## 개발 주의사항

- GUI MainThread에서 `cv2.VideoCapture.read()`를 반복 호출하지 않는다.
- 모델 추론은 MainThread에서 실행하지 않는다.
- Worker는 GUI 위젯을 직접 수정하지 않고 signal로 상태, 결과, 오류를 전달한다.
- SystemController는 상태 전이와 signal 중계를 담당한다.
- `CNNmodel.py`는 import만으로 모델 로드, 샘플 추론, plot 실행을 하지 않는다.
- prediction dict 형식은 `result_processor.py`와 맞춰야 한다.
- 모델 파일, 개인 이미지, 대용량 산출물, `.env` 파일은 Git에 포함하지 않는다.
- 문서 파일 인코딩은 UTF-8을 유지한다.

권장 prediction 형식:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```
