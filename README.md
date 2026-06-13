# Real-time Face Age & Gender Predictor

> PyQt5 GUI와 딥러닝(CNN) 기반의 실시간 얼굴 나이 및 성별 예측 시스템  
> SSU AI소프트웨어학부 2026년 1학기 고급AI수학 팀 프로젝트

## 프로젝트 개요

이 프로젝트는 웹캠으로 얼굴을 감지하고, 캡처한 얼굴 프레임을 기반으로 나이와 성별을 예측하는 Python 기반 애플리케이션입니다.
PyQt5 GUI가 `SystemController`/카메라 Worker/추론 Worker/결과 후처리 흐름에 연결되어, GUI에서 카메라 미리보기·측정·결과 표시까지 진행할 수 있습니다. 카메라 읽기와 모델 추론은 WorkerThread에서, 화면 표시는 MainThread에서 수행됩니다.

## 주요 기능

- OpenCV 기반 웹캠 얼굴 감지
- 얼굴 감지 상태 안정화 후 측정 준비 상태 판단
- 측정 요청 시 40프레임 캡처
- PyQt5 QThread 기반 카메라/명령 입력/추론 작업 분리
- 프레임별 예측 결과를 평균내는 후처리 구조
- TorchScript `.pt` 모델을 이용한 나이 및 성별 예측 실험 코드

## 기술 스택

- **Language**: Python 3.10+
- **GUI Framework**: PyQt5
- **Computer Vision**: OpenCV-Python, MediaPipe
- **Deep Learning**: PyTorch, TorchVision
- **Test**: pytest

## 프로젝트 구조

```text
ssuaisw-2026-face-age-and-gender-predictor/
├─ .github/
│  ├─ workflows/
│  │  └─ tests.yml
│  └─ pull_request_template.md
├─ docs/
│  ├─ overview.md
│  ├─ architecture.md
│  ├─ components.md
│  └─ development.md
├─ models/
│  └─ Best_Age_Estimate_model_traced.pt
├─ src/
│  └─ face_age_gender_predictor/
│     ├─ app/
│     │  ├─ main_app.py
│     │  └─ workers.py
│     ├─ camera/
│     │  └─ camera_detector.py
│     ├─ inference/
│     │  └─ CNNmodel.py
│     └─ processing/
│        └─ result_processor.py
├─ tests/
│  ├─ test_camera_detector.py
│  └─ test_run.py
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

Windows CMD:

```cmd
.venv\Scripts\activate
```

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

프로젝트와 개발용 의존성을 설치합니다.

```bash
python -m pip install -e ".[dev]"
```

## AI 모델 가중치

본 프로젝트를 실행하려면 학습된 TorchScript 모델 가중치 파일(`.pt`)이 필요합니다.
아래 링크에서 다운로드한 뒤 `models/` 폴더에 넣어주세요.

- [Best_Age_Estimate_model_traced.pt 다운로드](https://github.com/dddyoung2/ssuaisw-2026-face-age-and-gender-predictor/releases/download/v1.0.0/Best_Age_Estimate_model_traced.pt)

권장 위치:

```text
models/Best_Age_Estimate_model_traced.pt
```

모델 파일은 용량이 크기 때문에 Git에 커밋하지 않습니다.

## 실행 방법

메인 앱은 PyQt5 GUI 진입점입니다. 아래 명령으로 GUI 창을 띄웁니다.

```bash
python -m face_age_gender_predictor.app.main_app
```

GUI에서 "카메라 시작" → 얼굴 준비 후 "측정 시작" 순서로 동작하며, 카메라와 추론은 WorkerThread에서 실행됩니다. 카메라를 사용하는 실행은 노트북/웹캠이 연결된 데스크톱 환경에서 확인합니다. (실제 추론에는 `models/` 아래 TorchScript 모델 파일이 필요합니다.)

## 테스트

pytest 설정은 `pyproject.toml`에 정의되어 있습니다.

```bash
python -m pytest
```

현재 `tests/` 안의 파일은 카메라를 사용하는 수동 확인 성격이 강합니다.
웹캠이 없는 환경에서는 카메라 관련 테스트가 실패하거나 대기할 수 있습니다.
추후 자동 테스트는 카메라 의존성을 제거하거나 mock 기반 테스트로 분리할 예정입니다.

## 문서

상세 문서는 `docs/` 폴더에서 관리합니다.

- `docs/overview.md`: 프로젝트 목적과 사용자 흐름
- `docs/architecture.md`: 전체 구조와 데이터 흐름
- `docs/components.md`: 주요 모듈별 역할
- `docs/development.md`: 설치, 실행, 테스트, 개발 규칙

## AI Agent 작업 지침

AI agent가 프로젝트를 이해하고 일관된 방식으로 작업할 수 있도록 다음 파일을 둡니다.

- `AGENTS.md`: 공통 agent 작업 규칙
- `CLAUDE.md`: Claude 계열 agent 참고 규칙

## 현재 상태

- 프로젝트 구조를 `src/` 기반 Python 패키지 형태로 정리했습니다.
- GUI ↔ SystemController ↔ 카메라/추론 Worker(QThread) 연결이 완료되어, `main_app`이 GUI 진입점입니다.
- 실제 웹캠/GUI 수동 QA는 노트북 환경에서 진행할 예정입니다.
- 추론 워커는 현재 실제 모델 연동 전 임시 예측 흐름을 포함합니다(데이터 계약과 오류 전달 경로는 준비됨).
