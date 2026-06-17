# ACCEPTANCE

이 작업은 아래 조건을 만족하면 완료로 본다.

## Scope

- [ ] 구현자는 이 작업이 "GUI 나이 확신도 표시 공식 변경 + result_processor 성별 집계 기준 확인/필요 시 최소 수정" 범위임을 확인했다.
- [ ] 이전 모델 연결/반복 측정 PASS 작업을 불필요하게 재구현하지 않았다.
- [ ] gender confidence 정책은 변경하지 않았다.
- [ ] 기존 age 평균 집계 방식은 변경하지 않았다.
- [ ] 유효 prediction 30개 미만 실패 조건은 변경하지 않았다.
- [ ] 모델 파일, 모델 학습, 모델 weight는 변경하지 않았다.
- [ ] 광범위한 UI 리디자인을 하지 않았다.

## Formula

- [ ] age confidence는 26-bin 나이 분포를 기준으로 계산된다.
- [ ] 나이 bin은 `15..40` inclusive로 해석된다.
- [ ] normalized `age_probs`는 검증 후 사용된다.
- [ ] unnormalized positive weights는 normalize 후 사용된다.
- [ ] raw logits를 사용해야 하는 경우 softmax 후 사용된다.
- [ ] weighted mean은 `sum(weight * age)`로 계산된다.
- [ ] weighted standard deviation은 `sqrt(sum(weight * (age - mean)^2))`로 계산된다.
- [ ] `STDDEV_BEST = 1.57`이 사용된다.
- [ ] `STDDEV_WORST = 8.23`이 사용된다.
- [ ] `CONFIDENCE_BEST = 99.0`이 사용된다.
- [ ] `CONFIDENCE_WORST = 1.0`이 사용된다.
- [ ] confidence는 inverse linear mapping으로 계산된다.
- [ ] valid distribution의 최종 confidence는 `[1.0, 99.0]`로 clamp된다.

## Behavior

- [ ] 기존 predicted-age `±2`세 probability mass 방식은 displayed age confidence에 더 이상 사용되지 않는다.
- [ ] standard deviation이 `1.57`이면 age confidence가 `99%`로 표시된다.
- [ ] standard deviation이 `8.23`이면 age confidence가 `1%`로 표시된다.
- [ ] standard deviation이 `1.57`보다 낮으면 `99%`로 clamp된다.
- [ ] standard deviation이 `8.23`보다 높으면 `1%`로 clamp된다.
- [ ] uniform distribution over ages `15..40`은 낮은 confidence를 만든다.
- [ ] invalid distribution은 높은 confidence를 만들지 않는다.
- [ ] missing/empty/wrong-length/non-finite/non-normalizable input은 `0%`, `-`, 또는 명확한 unavailable 상태가 된다.
- [ ] 성공 result 표시 경로에서 새 confidence 값이 사용된다.
- [ ] GUI percentage 표시 형식은 기존 UI와 일관된다.
- [ ] age histogram 시각화는 유지된다.
- [ ] gender confidence 표시는 기존과 동일하다.

## result_processor Gender Aggregation

- [ ] prediction dict의 `gender` 값은 프레임별 성별 예측 점수로 해석된다.
- [ ] 성별 최종 집계는 유효 prediction만 필터링한 뒤 수행된다.
- [ ] 유효 prediction들의 `gender` score 평균값이 계산된다.
- [ ] `average_gender >= 0.5`이면 최종 `gender`는 `1`이다.
- [ ] `average_gender < 0.5`이면 최종 `gender`는 `0`이다.
- [ ] `average_gender == 0.5` 경계값은 최종 `gender == 1`로 처리된다.
- [ ] 앱 내부 label contract는 `gender == 1 -> 여성`, `gender == 0 -> 남성`으로 문서화되어 있다.
- [ ] `result_processor` 로그 또는 문서가 `1=여성`, `0=남성` 의미와 일치한다.
- [ ] GUI 결과 표시가 `gender == 1`을 `여성`, `gender == 0`을 `남성`으로 표시한다.
- [ ] 모델 출력 label 자체가 `1=여성`, `0=남성`인지 코드상 보장되지 않는 경우 `IMPLEMENTATION.md`에 Not Verified 또는 Follow-up으로 기록된다.
- [ ] 기존 age 평균 집계 방식은 유지된다.
- [ ] 기존 `gender_confidence` 평균 집계 방식은 유지된다.
- [ ] 유효 prediction이 30개 미만이면 gender 평균값과 무관하게 실패 result가 반환된다.
- [ ] prediction/result dict contract는 breaking change되지 않았다.
- [ ] 문서, 구현, 테스트가 위 성별 집계 기준과 서로 모순되지 않는다.

## Tests

- [ ] age confidence 계산 helper 또는 equivalent path에 대한 단위 테스트가 있다.
- [ ] stddev `1.57 -> 99%` 테스트가 있다.
- [ ] stddev `8.23 -> 1%` 테스트가 있다.
- [ ] stddev lower-bound clamp 테스트가 있다.
- [ ] stddev upper-bound clamp 테스트가 있다.
- [ ] uniform 15..40 distribution low-confidence 테스트가 있다.
- [ ] invalid input이 high confidence를 만들지 않는 테스트가 있다.
- [ ] 기존 `±2`세 window confidence를 기대하던 테스트가 새 공식 기준으로 갱신되었다.
- [ ] GUI result 표시 경로가 새 공식 helper를 사용하는지 확인하는 테스트가 있다.
- [ ] `result_processor`에서 `average_gender >= 0.5 -> gender == 1` 테스트가 있다.
- [ ] `result_processor`에서 `average_gender < 0.5 -> gender == 0` 테스트가 있다.
- [ ] `result_processor`에서 `average_gender == 0.5 -> gender == 1` 경계 테스트가 있다.
- [ ] GUI 표시 또는 관련 테스트에서 `gender == 1 -> 여성`, `gender == 0 -> 남성` contract가 확인된다.
- [ ] `result_processor`에서 age 평균 집계가 유지되는지 확인하는 테스트가 있다.
- [ ] `result_processor`에서 `gender_confidence` 평균 집계가 유지되는지 확인하는 테스트가 있다.
- [ ] `result_processor`에서 유효 prediction 30개 미만 실패 조건이 유지되는지 확인하는 테스트가 있다.
- [ ] 전체 자동 테스트가 통과한다.

## Documentation

- [ ] `AI-Agents/IMPLEMENTATION.md`에 변경 요약이 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 변경 파일이 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 표준편차 공식과 confidence mapping이 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 result_processor 성별 최종 집계 기준 확인/수정 결과가 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 테스트 명령과 결과가 기록되었다.
- [ ] `AI-Agents/IMPLEMENTATION.md`에 미검증 항목 또는 후속 작업이 기록되었다.
- [ ] `AI-Agents/REVIEW.md`는 Codex QA 대기 템플릿 상태로 남겨졌다.
- [ ] `AI-Agents/PR.md`는 Codex Release 대기 템플릿 상태로 남겨졌다.

## Guardrails

- [ ] `.env`, secret, 개인 이미지, 대용량 모델 파일이 추가/수정되지 않았다.
- [ ] `models/*.pt`, `models/*.pth`, `models/*.onnx`가 수정/stage 대상이 아니다.
- [ ] Git commit/push/PR을 수행하지 않았다.
- [ ] 관련 없는 문서나 시스템 파일을 수정하지 않았다.
- [ ] result dict contract를 breaking change하지 않았다.
