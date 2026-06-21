# GitHub Actions 로 1시간마다 자동 실행하기

> repo 에는 개인정보가 들어가지 않습니다.
> - 한전 ID/PW·텔레그램 토큰 → **Secrets**(암호화)
> - 요금값(state.json) → **Actions 캐시** (repo 아님)
> 그래서 **공개(public) repo** 로 올려도 안전하고, 공개면 Actions 가 **무료 무제한**입니다.

---

## 1단계 — GitHub 에 빈 repo 만들기

1. https://github.com/new 접속
2. **Repository name**: `powerplanner`
3. **Public** 선택
4. README/.gitignore/license 는 **추가하지 않음** (체크 해제)
5. **Create repository**

## 2단계 — Secrets 4개 등록

만든 repo 에서 **Settings → Secrets and variables → Actions → New repository secret** 으로 아래 4개를 추가:

| Name | Value |
|------|-------|
| `KEPCO_ID` | 한전 아이디 |
| `KEPCO_PW` | 한전 비밀번호 |
| `TELEGRAM_BOT_TOKEN` | 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 7287870674 |

> 이름은 **대소문자까지 정확히** 위와 같아야 합니다.

## 3단계 — 코드 푸시

이 폴더에서 (아래 `<당신아이디>` 를 본인 GitHub 아이디로):

```bash
git remote add origin https://github.com/<당신아이디>/powerplanner.git
git branch -M main
git push -u origin main
```

푸시할 때 GitHub 로그인(브라우저 인증 또는 토큰)이 필요합니다.

## 4단계 — 수동 실행으로 테스트 ★중요

1. repo 의 **Actions** 탭 클릭
2. (처음이면) "I understand my workflows, enable them" 클릭
3. 왼쪽 **파워플래너 전기요금 알림** 선택 → 오른쪽 **Run workflow** → **Run workflow**
4. 1~2분 뒤 실행이 **초록색 ✓** 이면 성공 — 텔레그램으로 요금이 옵니다.
5. **빨간색 ✗** 이면 (해외 IP 차단 가능성) → 실행 로그 + Artifacts 의 `capture` 를 확인.
   차단이면 맥 launchd 또는 Oracle Cloud 서울 VM 으로 전환하면 됩니다.

## 자동 실행 주기

- 성공하면 그 뒤로는 **매시간 자동** 실행됩니다 (`.github/workflows/powerplanner.yml` 의 cron).
- 원할 때 수동 실행은 위 4단계의 **Run workflow** 버튼.

> ⚠️ 공개 repo 라도 **60일간 아무 커밋이 없으면** 스케줄이 멈춥니다.
> 가끔 커밋 한 번 하거나, 멈추면 Run workflow 로 깨우면 됩니다.

## 알림 주기 바꾸기

- 매시간 무조건 받고 싶으면: 워크플로우의 `NOTIFY_ON_CHANGE_ONLY: "true"` → `"false"`
- 주기를 바꾸려면: `cron: "5 * * * *"` 수정 (예: 30분마다 `"*/30 * * * *"`)
