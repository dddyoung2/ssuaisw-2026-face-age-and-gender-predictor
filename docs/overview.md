# Project Overview

## 목적

이 프로젝트는 웹캠으로 사용자의 얼굴을 감지하고, 짧은 시간 동안 수집한 얼굴 프레임을 TorchScript CNN 모델로 분석해 나이와 성별을 예측하는 PyQt5 데스크톱 애플리케이션입니다.

프로젝트의 핵심 목표는 단일 이미지 예측보다 안정적인 결과를 제공하는 것입니다. 이를 위해 얼굴이 정상적으로 감지된 상태에서 40프레임을 캡처하고, 프레임별 예측값을 후처리해 최종 결과를 표시합니다.

## 대상 사용자

- 팀 프로젝트 시연자와 평가자
- 웹캠 기반 AI 추론 GUI를 확인하려는 개발자
- 실시간 얼굴 감지, QThread 분리, 모델 추론 연결 흐름을 검증하려는 QA 담당자

## 사용자 흐름

```text
1. 사용자가 GUI 앱을 실행한다.
2. 사용자가 카메라 시작 버튼을 누른다.
3. 앱이 웹캠 프레임을 표시하고 얼굴 감지 상태를 안내한다.
4. 얼굴이 안정적으로 감지되면 측정 시작 버튼이 활성화된다.
5. 사용자가 측정 시작 버튼을 누르면 버튼이 잠기고 카운트다운이 시작된다.
6. 카운트다운 종료 시점에 얼굴 상태를 다시 확인한다.
7. 정상 상태이면 40프레임을 캡처한다.
8. 추론 Worker가 TorchScript 모델로 프레임별 예측을 수행한다.
9. result_processor가 예측값을 집계한다.
10. GUI가 얼굴 미리보기, 나이, 성별, 신뢰도, 나이 분포를 표시한다.
11. 결과 화면은 유지된다.
12. 얼굴이 다시 정상 인식되면 다음 측정 시작 버튼이 다시 활성화된다.
13. 사용자가 재활성화된 측정 시작 버튼을 누르면 이전 결과 표시를 초기화하고 새 측정을 시작한다.
```

## 주요 기능

- PyQt5 기반 GUI
- OpenCV/MediaPipe 기반 실시간 카메라 프레임 처리
- 얼굴 감지 상태에 따른 측정 가능 여부 판단
- 측정 시작 전 카운트다운과 얼굴 상태 재검증
- 40프레임 메모리 캡처
- TorchScript `.pt` 모델 기반 나이/성별 추론
- QThread 기반 카메라 작업과 추론 작업 분리
- 프레임별 prediction dict 후처리
- 성공/실패 결과 표시와 반복 측정 흐름

## 현재 구현 기준

```text
main_app.py
= QApplication, SystemController, AgeEstimatorWindow를 생성하고 signal/slot으로 연결하는 공식 GUI 진입점

main_window.py / AgeEstimatorWindow
= 화면 표시와 사용자 입력을 담당하는 View

SystemController
= 앱 상태 전이, 카운트다운, 카메라 Worker, 추론 Worker 연결을 담당

CameraBridgeWorker / CameraDetector
= CameraThread에서 카메라 프레임 읽기, 얼굴 감지, 40프레임 캡처를 수행

InferenceWorker
= InferenceThread에서 CNNmodel.predict_frames()와 result_processor를 호출

CNNmodel.py
= import-safe 앱용 추론 API와 TorchScript 모델 로드/캐시를 제공

result_processor.py
= prediction list를 최종 result dict로 집계
```

## 포함 범위

- GUI와 SystemController 연결
- 카메라 미리보기와 얼굴 감지 상태 표시
- 측정 버튼, 카운트다운, 캡처 진행률, 결과 표시
- CameraThread와 InferenceThread 분리
- `models/Best_Age_Estimate_model_traced.pt` 기반 실제 추론 연결
- 반복 측정 흐름
- 자동 테스트와 수동 QA 체크 기준

## 제외 범위

- 모델 재학습
- 데이터셋 수집 또는 라벨링
- 모델 파일 Git 커밋
- 대규모 UI 리디자인
- 웹/모바일 배포
- 성능 최적화 실험

## 현재 검증 상태

- 자동 테스트는 pytest로 실행한다.
- 모델 파일이 로컬에 있을 때 TorchScript 모델 로드와 smoke 추론을 확인할 수 있다.
- 실제 웹캠 GUI 전체 흐름은 카메라가 연결된 로컬 환경에서 수동 QA가 필요하다.
