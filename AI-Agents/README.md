# AI-Agents

이 폴더는 Claude Code와 Codex를 함께 사용할 때 작업 지시, 완료 기준, 구현 보고, QA, 릴리즈 참고 자료를 분리해 관리하는 공간이다. Claude Code는 PR 본문이나 `PR.md`를 작성하지 않는다.

## 역할

```text
Claude Code
= 구현 담당 Programming Agent

Codex Planning
= TASK / ACCEPTANCE 검토

Codex QA
= 변경사항 검토와 REVIEW 작성

Codex Release
= 테스트 확인, commit/push/PR 준비

사람
= 문제 정의, 최종 승인, merge 판단
```

## 파일 역할

| 파일 | 역할 | 커밋 |
| --- | --- | --- |
| `README.md` | AI-Agents 폴더 운영법 | commit |
| `TASK.md` | 이번 작업 지시서 | commit 가능 |
| `ACCEPTANCE.md` | 완료 판정 기준 | commit 가능 |
| `IMPLEMENTATION.md` | Claude 구현 보고서 | 선택 |
| `REVIEW.md` | Codex QA 보고서 | 선택 |
| `PR.md` | 사용자/Codex Release 전용 릴리즈 메모, Claude 수정 금지 | 선택 |
| `archive/` | 완료된 작업 기록 보관 | 보통 `.gitignore` |

## 현재 작업 주제

이번 작업은 GUI 통합 단계다.

1. 업로드된 GUI 코드를 현재 시스템에 부착한다.
2. GUI와 프로젝트 코드가 QThread 기반으로 안전하게 분리되어 동작하게 한다.
3. 정상 작동 여부를 QA 테스트한다.

## 기본 운영 흐름

```text
1. 사람이 TASK 목표를 정의한다.
2. Codex Planning이 TASK.md / ACCEPTANCE.md를 점검한다.
3. Claude Code가 구현한다.
4. Claude Code가 IMPLEMENTATION.md를 작성한다.
5. Codex QA가 diff와 테스트를 검토하고 REVIEW.md를 작성한다.
6. NEEDS_FIX면 Claude Code가 수정한다.
7. PASS면 사용자 또는 Codex Release가 GitHub 작업을 준비한다.
```

## 필수 참고 문서

- `README.md`
- `docs/overview.md`
- `docs/SPEC.md`
- `docs/architecture.md`
- `docs/components.md`
- `docs/development.md`
- `docs/team-tasks.md`
- `AI-Agents/TASK.md`
- `AI-Agents/ACCEPTANCE.md`

## Notion 기준 보강 결과

`Project Initial Setting: Github/repository and AI agent` 기준으로 현재 프로젝트에 부족했던 점은 다음처럼 보강했다.

- `docs/SPEC.md`를 추가해 GUI 통합, QThread 분리, QA 테스트의 정본 명세를 만들었다.
- 5개 역할 기준으로 `docs/team-tasks.md`를 추가해 GUI, QThread, CNN model, inference/camera, 전처리 담당 영역과 합의 필요 영역을 분리했다.
- `AI-Agents/` 문서를 `TASK`, `ACCEPTANCE`, `IMPLEMENTATION`, `REVIEW` 중심으로 재구성했다.
- `PR.md`는 Claude 작업 흐름에서 제외하고 사용자/Codex Release 전용 참고 파일로 분리했다.
- `.gitignore`에서 선택 기록 파일인 `IMPLEMENTATION.md`, `REVIEW.md`, `archive/`만 제외하도록 정리했다.

추가 개선 후보는 다음과 같다.

- `docs/git-workflow.md`
- `CONTRIBUTING.md`
- `docs/decisions/`
- `docs/ai-prompts/`
- `docs/session-handoff.md`

## 원칙

- 한 작업은 한 TASK와 한 QA 결과로 관리한다.
- 구현과 QA의 책임을 분리한다.
- Claude는 PR 본문, GitHub PR, `AI-Agents/PR.md`를 작성하거나 갱신하지 않는다.
- GUI, 카메라, 추론, 후처리의 경계를 흐리지 않는다.
- 시크릿, 개인 이미지, 모델 파일, 대용량 산출물은 커밋하지 않는다.
- 관련 없는 리팩터링은 하지 않는다.
