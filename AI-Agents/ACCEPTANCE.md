# ACCEPTANCE

이 작업은 아래 조건을 만족하면 완료로 본다.

## Core

- [ ] 업로드된 GUI 코드가 프로젝트 패키지 구조에 부착되었다.
- [ ] `python -m face_age_gender_predictor.app.main_app` 실행 시 PyQt5 GUI 창이 열린다.
- [ ] GUI에서 카메라 미리보기가 표시된다.
- [ ] 얼굴 감지 상태가 GUI에 표시된다.
- [ ] 얼굴 준비 완료 상태에서 측정 버튼을 누를 수 있다.
- [ ] 측정 시작 후 버튼 중복 클릭이 막힌다.
- [ ] 카운트다운이 GUI에 표시된다.
- [ ] 카운트다운 종료 시점 또는 촬영 시작 직전에 얼굴 상태가 재검증된다.
- [ ] 40프레임 캡처가 CameraWorker 경로로 실행된다.
- [ ] 캡처 완료 후 InferenceWorker/CNNmodel/result_processor 경로로 이어진다.
- [ ] 추론 작업이 GUI MainThread가 아닌 InferenceWorker 경로로 실행된다.
- [ ] `models/Best_Age_Estimate_model_traced.pt`가 기본 모델 경로로 사용된다.
- [ ] InferenceWorker가 임시 prediction이 아니라 `CNNmodel.py`의 앱용 추론 API를 호출한다.
- [ ] 최종 결과 또는 실패 메시지가 GUI에 표시된다.
- [ ] 성공/실패 후 재측정 가능한 상태로 돌아간다.
- [ ] 창 종료 시 카메라와 QThread가 정리된다.

## Threading

- [ ] GUI 위젯 업데이트는 MainThread에서만 수행된다.
- [ ] CameraBridgeWorker는 CameraThread에서 실행된다.
- [ ] InferenceWorker는 별도 InferenceThread에서 실행된다.
- [ ] Worker가 GUI 위젯을 직접 수정하지 않는다.
- [ ] GUI가 `cv2.VideoCapture.read()` 반복 호출이나 모델 추론을 직접 수행하지 않는다.
- [ ] TorchScript 모델 로드와 추론은 GUI MainThread에서 실행되지 않는다.
- [ ] 중복 촬영 또는 중복 추론 요청이 방지된다.
- [ ] 종료 또는 오류 후 남은 QThread가 재사용/종료 불가능한 상태로 남지 않는다.

## Data Contract

- [ ] `CNNmodel.py`를 import해도 샘플 추론, 그래프 출력, 모델 로드 같은 side effect가 자동 실행되지 않는다.
- [ ] `CNNmodel.py`가 `predict_frames(frames: list) -> list[dict]` 또는 이에 준하는 앱용 API를 제공한다.
- [ ] prediction dict 형식이 `docs/SPEC.md`와 호환된다.
- [ ] result dict 형식이 `docs/SPEC.md`와 호환된다.
- [ ] `valid_count >= 30`이면 성공 result로 처리된다.
- [ ] `valid_count < 30`이면 실패 result와 reason이 GUI에 표시 가능한 형태로 전달된다.
- [ ] 모델 파일 없음, 모델 로드 실패, 전처리 실패, 추론 실패가 앱 크래시 없이 GUI 오류 또는 실패 result로 전달된다.

## Tests

- [ ] 관련 자동 테스트가 통과한다.
- [ ] 자동화가 어려운 GUI/카메라 흐름은 수동 QA 결과가 기록된다.
- [ ] 정상 케이스가 확인되었다.
- [ ] 얼굴 없음 케이스가 확인되었다.
- [ ] 카운트다운 중 얼굴 사라짐 케이스가 확인되었다.
- [ ] 실제 `.pt` 모델 연결 추론 경로가 확인되었다.
- [ ] 추론 실패 또는 모델 파일 없음 케이스가 앱 크래시가 아닌 GUI 오류로 처리되는지 확인되었다.
- [ ] 종료 처리 케이스가 확인되었다.

## Documentation

- [ ] `IMPLEMENTATION.md`가 작성되었다.
- [ ] `REVIEW.md` Verdict가 PASS 또는 명확한 BLOCKED다.
- [ ] 수동 QA 결과가 `IMPLEMENTATION.md`에 기록되었다.
- [ ] 필요한 경우에만 `docs/SPEC.md` 또는 관련 문서가 최소 갱신되었다.

## Guardrails

- [ ] 수정 금지 파일을 건드리지 않았다.
- [ ] 모델 파일, 개인 이미지, 시크릿이 커밋 대상에 포함되지 않았다.
- [ ] 관련 없는 리팩터링을 하지 않았다.
- [ ] 모델 파일 자체를 수정하거나 커밋 대상으로 만들지 않았다.
- [ ] 모델 재학습, 대규모 전처리 재작성, UI 리디자인을 하지 않았다.
- [ ] prediction/result dict 형식을 임의로 바꾸지 않았다.
- [ ] main 브랜치에 직접 push하지 않았다.
- [ ] Claude가 GitHub PR, PR 본문, `AI-Agents/PR.md`를 작성하거나 갱신하지 않았다.
