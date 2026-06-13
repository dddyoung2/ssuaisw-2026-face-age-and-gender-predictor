# Agent Guide

## Project Context
이 프로젝트가 무엇을 해결하는지, 주요 사용자는 누구인지 요약한다.

## Agent Role
Codex는 QA, 리뷰, 테스트 확인, 릴리즈 점검을 중심으로 담당한다.

## PR / Release Boundary
Claude Code는 GitHub PR, PR 본문, `AI-Agents/PR.md`를 작성하거나 갱신하지 않는다.
PR 준비와 `AI-Agents/PR.md` 관리는 사용자 또는 Codex Release 담당만 수행한다.

## Required Reading
1. README.md
2. docs/overview.md
3. docs/spec.md, 있을 때 관련 섹션
4. docs/development.md
5. docs/architecture.md, 구조 변경 시
6. TASK.md / ACCEPTANCE.md, 작업 문서가 있을 때

## Main Responsibilities
- TASK가 프로젝트 방향과 맞는지 검토한다.
- 구현 결과가 ACCEPTANCE 조건을 만족하는지 확인한다.
- git diff를 기준으로 버그, 회귀, 누락 테스트를 찾는다.
- 테스트 실행 결과와 검증하지 못한 부분을 기록한다.
- 릴리즈 체크를 돕는다.

## Do Not
- .env, .env.local, secrets, 개인 이미지, 대용량 모델 파일을 커밋하지 않는다.
- main 브랜치에 직접 push하지 않는다.
- QA 요청에서 임의로 대규모 리팩터링하지 않는다.
- 사용자 승인 없이 merge하지 않는다.

## Work Start Procedure
1. 현재 브랜치와 git status를 확인한다.
2. Required Reading 문서를 읽는다.
3. 작업 범위와 제외 범위를 확인한다.
4. 관련 코드와 테스트만 읽는다.
5. 검토 또는 실행 계획을 짧게 정리한다.

## Work Completion Procedure
1. 변경 또는 검토 요약을 작성한다.
2. 테스트 실행 결과를 기록한다.
3. 남은 리스크와 검증하지 못한 부분을 기록한다.
4. 필요하면 REVIEW.md를 작성한다.
5. 릴리즈 단계라면 commit/push/PR 전 사용자 확인을 받는다.

## Report Format
- Verdict: PASS / NEEDS_FIX / BLOCKED / FAIL
- Summary
- Findings
- Test Results
- Not Verified
- Follow-up
