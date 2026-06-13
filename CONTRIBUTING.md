# Contributing

## 작업 원칙

- 한 작업은 한 브랜치와 한 PR로 관리한다.
- `main` 브랜치에 직접 commit 또는 push하지 않는다.
- 항상 최신 `main`에서 새 브랜치를 만든다.
- 시크릿, 개인정보, 개인 이미지, 대용량 모델 파일은 commit하지 않는다.
- PR 전 테스트 결과와 문서 갱신 여부를 확인한다.

## 브랜치 네이밍

- `feat/short-description`
- `fix/short-description`
- `refactor/short-description`
- `docs/short-description`
- `test/short-description`
- `chore/short-description`

## 커밋 메시지

권장 형식:

`type(scope): summary`

예시:

- `feat(auth): 로그인 화면 추가`
- `fix(camera): 카메라 초기화 오류 수정`
- `docs(readme): 실행 방법 갱신`
- `test(processing): 결과 집계 테스트 추가`
- `chore(project): pyproject 설정 추가`

## Pull Request 규칙

PR에는 다음 내용을 포함한다.

- 변경 요약
- 왜 필요한가
- 테스트 결과
- 관련 문서
- 리뷰어가 볼 점
- 실행하지 못한 검증과 그 이유

## 테스트 규칙

- 자동화 가능한 테스트는 PR 전 실행한다.
- 카메라, GPU, GUI, 개인 이미지가 필요한 테스트는 수동 테스트로 분리한다.
- 실행하지 못한 테스트는 PR에 이유를 기록한다.

## 보안 규칙

다음 항목은 commit하지 않는다.

- `.env`
- `.env.local`
- API key
- access token
- private key
- 운영 DB dump
- 개인 사진
- 개인정보 포함 데이터
- 대용량 모델 파일
- 로컬 가상환경 폴더