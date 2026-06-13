# Real-time Face Age & Gender Predictor

> PyQt5 GUI와 TorchScript CNN 모델 기반의 실시간 얼굴 나이 및 성별 예측 시스템  
> SSU AI소프트웨어학부 2026년 1학기 고급AI수학 팀 프로젝트

## 프로젝트 개요

이 프로젝트는 웹캠으로 얼굴을 감지하고, 정상적으로 감지된 얼굴 프레임을 캡처한 뒤 나이와 성별을 예측하는 Python 데스크톱 애플리케이션입니다.

현재 앱은 PyQt5 GUI, `SystemController`, 카메라 Worker, 추론 Worker, 결과 후처리 모듈로 분리되어 있습니다. GUI는 MainThread에서 화면 표시와 사용자 입력만 담당하고, 카메라 읽기와 모델 추론은 QThread 기반 Worker에서 실행됩니다.

## 주요 기능

- OpenCV/MediaPipe 기반 웹캠 얼굴 감지
- 얼굴 감지 안정화 후 측정 버튼 활성화
- 측정 요청 시 40프레임 캡처
- TorchScript `.pt` 모델을 이용한 나이/성별 추론
- 프레임별 예측값을 평균내는 결과 후처리
- 정상 측정 완료 후 재인식되면 다음 측정을 시작할 수 있는 반복 측정 흐름
- PyQt5 QThread 기반 카메라/추론 작업 분리
- GUI 결과 화면에 얼굴 미리보기, 나이, 성별, 신뢰도, 나이 분포 표시

## 기술 스택

- **Language**: Python 3.10+
- **GUI Framework**: PyQt5
- **Computer Vision**: OpenCV-Python, MediaPipe
- **Deep Learning**: PyTorch, TorchVision, TorchScript
- **Test**: pytest

## 프로젝트 구조

```text
ssuaisw-2026-face-age-and-gender-predictor/
├─ AI-Agents/
│  ├─ ACCEPTANCE.md
│  ├─ IMPLEMENTATION.md
│  ├─ PR.md
│  ├─ REVIEW.md
│  └─ TASK.md
├─ docs/
│  ├─ SPEC.md
│  ├─ architecture.md
│  ├─ components.md
│  ├─ development.md
│  ├─ overview.md
│  └─ team-tasks.md
├─ models/
│  └─ Best_Age_Estimate_model_traced.pt
├─ scripts/
│  ├─ test_camera_detector.py
│  └─ test_run.py
├─ src/
│  └─ face_age_gender_predictor/
│     ├─ app/
│     │  ├─ main_app.py
│     │  ├─ main_window.py
│     │  └─ workers.py
│     ├─ camera/
│     │  └─ camera_detector.py
│     ├─ inference/
│     │  └─ CNNmodel.py
│     └─ processing/
│        └─ result_processor.py
├─ tests/
│  ├─ conftest.py
│  ├─ test_camera_detector.py
│  ├─ test_cnnmodel.py
│  ├─ test_controller.py
│  ├─ test_main_window.py
│  ├─ test_result_processor.py
│  ├─ test_window_preview.py
│  └─ test_workers.py
├─ AGENTS.md
├─ CLAUDE.md
├─ pyproject.toml
└─ README.md
```

## 설치 방법

저장소를 클론한 뒤 프로젝트 루트로 이동합니다.

```bash
git clone https://github.com/dddyoung2/ssuaisw-2026-face-age-and-gender-predictor.git
cd ssuaisw-2026-face-age-and-gender-predictor
```

가상환경을 생성하고 활성화합니다.

```bash
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
.venv\Scripts\activate
```

프로젝트와 개발용 의존성을 설치합니다.

```bash
python -m pip install -e ".[dev]"
```

## AI 모델 가중치

실제 추론에는 학습된 TorchScript 모델 파일이 필요합니다. 모델 파일은 용량이 크므로 Git에 커밋하지 않고, `models/` 폴더 아래에 별도로 둡니다.

권장 위치:

```text
models/Best_Age_Estimate_model_traced.pt
```

다운로드:

- [Best_Age_Estimate_model_traced.pt](https://github.com/dddyoung2/ssuaisw-2026-face-age-and-gender-predictor/releases/download/v1.0.0/Best_Age_Estimate_model_traced.pt)

## 실행 방법

메인 GUI 진입점은 `main_app.py`입니다.

```bash
python -m face_age_gender_predictor.app.main_app
```

기본 사용자 흐름:

```text
카메라 시작 -> 얼굴 감지/준비 완료 -> 측정 시작 -> 40프레임 캡처 -> 모델 분석 -> 결과 표시
```

`main_window.py`는 GUI View를 담고 있으며 단독 실행도 가능하지만, 전체 카메라/추론 흐름은 `main_app.py`에서 `SystemController`와 연결될 때 동작합니다.

## 테스트

pytest 설정은 `pyproject.toml`에 정의되어 있습니다.

```bash
python -m pytest
```

현재 자동 테스트는 다음 영역을 다룹니다.

- `result_processor` 성공/실패 집계
- `CameraDetector` 캡처/상태 흐름
- `CNNmodel` import 안전성, 모델 경로, 추론 API 계약
- `InferenceWorker`와 `SystemController`의 결과 전달
- `main_window` 표시 로직, 나이 신뢰도, 얼굴 미리보기 스냅샷

실제 웹캠을 사용하는 GUI 전체 흐름은 로컬 장비와 모델 파일이 필요하므로 수동 QA로 별도 확인합니다.

## 문서

상세 문서는 `docs/` 폴더에서 관리합니다.

- `docs/overview.md`: 프로젝트 목적과 사용자 흐름
- `docs/SPEC.md`: 기능 요구사항과 QA 기준
- `docs/architecture.md`: 전체 구조, 스레드, 데이터 흐름
- `docs/components.md`: 주요 모듈별 역할
- `docs/development.md`: 설치, 실행, 테스트, 개발 규칙
- `docs/team-tasks.md`: 팀 역할과 작업 경계

## AI Agent 작업 지침

AI agent가 프로젝트를 이해하고 일관된 방식으로 작업할 수 있도록 다음 파일을 둡니다.

- `AGENTS.md`: 공통 agent 작업 규칙
- `CLAUDE.md`: Claude 계열 agent 참고 규칙
- `AI-Agents/`: TASK, ACCEPTANCE, IMPLEMENTATION, REVIEW, PR 산출물

## 현재 상태

- GUI와 `SystemController`, CameraThread, InferenceThread 연결이 완료되었습니다.
- `InferenceWorker`는 `CNNmodel.predict_frames()`를 통해 `models/Best_Age_Estimate_model_traced.pt` 기반 추론 경로를 사용합니다.
- `CNNmodel.py`는 import 시 모델 로드, 샘플 추론, plot 실행이 발생하지 않도록 앱용 API 중심으로 정리되어 있습니다.
- 정상 측정 1회 완료 후 얼굴을 다시 정상 인식하면 다음 측정 버튼이 활성화되는 흐름이 구현되어 있습니다.
- 실제 웹캠 환경에서의 최종 사용자 시나리오 QA는 로컬 장비 조건에 따라 별도 확인이 필요합니다.
