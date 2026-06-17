# Claude Code Guide

@AGENTS.md

## Project Context
이 프로젝트가 무엇을 해결하는지, 주요 사용자는 누구인지 요약한다.

## Agent Role
Claude Code는 구현, 리팩터링, 테스트 초안 작성을 중심으로 담당한다.
Claude Code는 PR 작성, PR 본문 초안 작성, `AI-Agents/PR.md` 작성/갱신을 하지 않는다.

## Required Reading
1. README.md
2. docs/overview.md
3. docs/spec.md, 있을 때 관련 섹션
4. docs/development.md
5. docs/architecture.md, 구조 변경 시
6. TASK.md / ACCEPTANCE.md, 작업 문서가 있을 때

## Main Responsibilities
- TASK.md와 ACCEPTANCE.md 범위 안에서 구현한다.
- 기존 구조와 스타일을 유지하면서 필요한 코드만 수정한다.
- 리팩터링은 요구사항 달성에 필요한 범위로 제한한다.
- 필요한 테스트 초안을 작성하거나 기존 테스트를 갱신한다.
- 작업 후 IMPLEMENTATION.md에 변경 요약과 테스트 결과를 기록한다.

## Do Not
- .env, .env.local, secrets, 개인 이미지, 대용량 모델 파일을 열람/수정/출력하지 않는다.
- main 브랜치에 직접 push하지 않는다.
- GitHub PR, PR 본문, `AI-Agents/PR.md`를 작성하거나 갱신하지 않는다.
- `AI-Agents/PR.md`는 어떤 경우에도 수정하지 않는다. PR 관련 내용은 `IMPLEMENTATION.md`의 Not Verified / Follow-up에만 기록한다.
- 사용자 승인 없는 대규모 리팩터링을 하지 않는다.
- QA 지적 범위를 넘어 새 기능을 임의 추가하지 않는다.

## Work Start Procedure
1. 현재 브랜치와 git status를 확인한다.
2. Required Reading 문서를 읽는다.
3. TASK.md와 ACCEPTANCE.md의 범위를 확인한다.
4. 관련 코드와 테스트만 읽는다.
5. 구현 계획을 짧게 정리한 뒤 작업한다.

## Work Completion Procedure
1. 구현 요약을 작성한다.
2. 수정 파일과 변경 이유를 기록한다.
3. 실행한 테스트와 결과를 기록한다.
4. 남은 리스크와 Codex QA가 확인할 부분을 기록한다.
5. IMPLEMENTATION.md를 작성하거나 갱신한다.

## Report Format
- Summary
- Changed Files
- Requirement Mapping
- Test Results
- Risks / Blocked
- Notes for Codex QA
