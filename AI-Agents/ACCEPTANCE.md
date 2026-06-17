# ACCEPTANCE

이 작업은 아래 조건을 만족하면 완료로 본다.

## Scope

- [ ] 구현자는 이 작업이 "GUI 디자인 변경"에 한정된 작업임을 확인했다.
- [ ] 첨부된 구버전 `main_window.py`를 코드 전체 교체본이 아니라 디자인 참고 자료로만 사용했다.
- [ ] 현재 출력/추론/집계 로직을 변경하지 않았다.
- [ ] 나이 확신도 계산 공식은 현행 표준편차 기반 방식을 유지했다.
- [ ] 성별 표시 contract와 result_processor 집계 정책을 변경하지 않았다.
- [ ] GitHub CI에서 실패했던 `average_gender == 0.5` 경계 케이스가 안정적으로 `gender == 1`을 반환한다.
- [ ] camera/worker/thread/timer/signal-slot 흐름을 변경하지 않았다.
- [ ] 모델 파일, 모델 학습, 모델 inference 코드를 변경하지 않았다.
- [ ] 새 기능 추가나 광범위한 구조 변경을 하지 않았다.

## Design Requirements

- [ ] GUI 전체가 밝은 블루/화이트 계열의 일관된 visual style을 갖는다.
- [ ] 주요 패널/카드/결과 영역은 옅은 border, 적절한 padding, readable한 contrast를 가진다.
- [ ] primary 버튼과 진행 표시가 light theme에 맞게 정리되어 있다.
- [ ] 측정 전/측정 중/결과 표시/실패 상태에서 버튼 스타일과 상태가 명확하다.
- [ ] preview image 또는 camera preview 영역이 깨지거나 찌그러지지 않는다.
- [ ] result metric card 또는 결과 표시 영역의 텍스트가 겹치지 않는다.
- [ ] histogram 영역은 배경과 구분되며 현재 값 표시가 읽기 쉽다.
- [ ] 작은 창 크기에서도 주요 라벨과 버튼 텍스트가 parent 영역 밖으로 넘치지 않는다.
- [ ] 카드 안에 불필요하게 중첩된 카드 구조를 만들지 않았다.

## Logic Preservation

- [ ] 나이 확신도는 26-bin 나이 분포의 weighted standard deviation 기반으로 계산된다.
- [ ] 표준편차 `1.57 -> 99%`, `8.23 -> 1%` mapping이 유지된다.
- [ ] confidence clamp 범위 `[1%, 99%]`가 유지된다.
- [ ] invalid `age_probs`가 높은 confidence로 fallback하지 않는다.
- [ ] 첨부 파일의 예전 predicted-age `±2` probability mass 방식이 되살아나지 않았다.
- [ ] age histogram의 값 생성/validity 처리 정책이 현행 로직과 일치한다.
- [ ] `gender == 1 -> 여성`, `gender == 0 -> 남성` 표시 contract가 유지된다.
- [ ] `gender_confidence` 표시 방식과 값 계산이 유지된다.
- [ ] `result_processor`의 `average_gender >= 0.5 -> 1`, `< 0.5 -> 0` 정책을 변경하지 않았다.
- [ ] 수학적으로 `average_gender == 0.5`인 입력이 부동소수점 합산 오차 때문에 `0`으로 판정되지 않는다.
- [ ] 성별 평균 안정화가 필요해 `result_processor.py`를 수정했다면, 정책 변경 없이 numeric stability 최소 수정으로만 처리했다.
- [ ] 기존 age 평균 집계 방식은 변경하지 않았다.
- [ ] 유효 prediction 30개 미만 실패 조건은 변경하지 않았다.
- [ ] result dict contract를 breaking change하지 않았다.

## Tests / Verification

- [ ] `main_window.py` 문법 검증 또는 import 검증을 수행했다.
- [ ] 관련 GUI 테스트가 있다면 실행했고 통과했다.
- [ ] `tests/test_result_processor.py`를 실행했고 GitHub CI 실패 케이스가 통과했다.
- [ ] 전체 pytest가 가능한 환경이면 실행했고 결과를 기록했다.
- [ ] 디자인 변경 때문에 기존 테스트를 수정했다면, 구버전 첨부 코드가 아니라 현행 로직 기준으로 수정했다.
- [ ] 성공 result 표시에서 나이, 성별, 성별 확신도, 나이 확신도, histogram이 표시되는지 확인했다.
- [ ] 실패 result 표시에서 앱이 멈추지 않고 버튼 상태가 복구되는지 확인했다.
- [ ] invalid `age_probs` 표시 정책이 깨지지 않았는지 확인했다.
- [ ] 수동 GUI QA를 수행하지 못했다면 `IMPLEMENTATION.md`의 Not Verified에 기록했다.

## Documentation

- [ ] `AI-Agents/IMPLEMENTATION.md`에 변경 요약이 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 변경 파일이 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 첨부 구버전 코드에서 반영한 디자인 요소가 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 변경하지 않은 로직과 그 이유가 기록되었다.
- [ ] GitHub CI 실패를 수정했다면 `AI-Agents/IMPLEMENTATION.md`에 원인, 수정 방식, 테스트 결과가 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 테스트 명령과 결과가 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 미검증 항목 또는 후속 작업이 기록되었다.
- [ ] `AI-Agents/REVIEW.md`는 Codex QA 대기 템플릿 상태로 남겨졌다.
- [ ] `AI-Agents/PR.md`는 Codex Release 대기 템플릿 상태로 남겨졌다.

## Guardrails

- [ ] `.env`, secret, 개인 이미지, 대용량 모델 파일이 추가/수정되지 않았다.
- [ ] `models/*.pt`, `models/*.pth`, `models/*.onnx`가 수정/stage 대상이 아니다.
- [ ] 빌드 산출물, 캐시 산출물, 임시 파일을 커밋 대상으로 만들지 않았다.
- [ ] Git commit/push/PR을 수행하지 않았다.
- [ ] 관련 없는 문서나 시스템 파일을 수정하지 않았다.
- [ ] `AI-Agents/PR.md`는 구현자가 작성/갱신하지 않았다.
