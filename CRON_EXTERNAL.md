# 외부 크론으로 매시간 확실하게 실행하기

GitHub 자체 스케줄(cron)은 무료 플랜에서 자주 지연·누락됩니다.
외부 무료 크론 서비스(**cron-job.org**)가 매시간 GitHub API를 호출해
워크플로우를 **확실하게** 깨우도록 만듭니다. (PC 불필요·무료)

---

## 1단계 — GitHub 토큰(PAT) 발급

워크플로우를 외부에서 실행시키려면 권한 토큰이 필요합니다.

1. https://github.com/settings/personal-access-tokens/new (Fine-grained token)
2. **Token name**: `powerplanner-cron`
3. **Expiration**: 원하는 만큼 (예: 1년)
4. **Repository access** → **Only select repositories** → `powerplanner` 선택
5. **Permissions** → **Repository permissions** → **Actions** → **Read and write** 로 설정
6. **Generate token** → 나온 토큰(`github_pat_...`) 복사 (한 번만 보임!)

---

## 2단계 — cron-job.org 에 등록

1. https://cron-job.org 가입(무료) → 로그인
2. **Create cronjob**
3. 설정:
   - **Title**: 파워플래너 매시간
   - **URL**:
     ```
     https://api.github.com/repos/mungiri/powerplanner/actions/workflows/powerplanner.yml/dispatches
     ```
   - **Schedule**: Every hour (매시간) — 예: 매시 5분
4. **Advanced(고급) 설정** 펼치기:
   - **Request method**: `POST`
   - **Request headers** 에 아래 3줄 추가:
     ```
     Authorization: Bearer github_pat_여기에_복사한토큰
     Accept: application/vnd.github+json
     X-GitHub-Api-Version: 2022-11-28
     ```
   - **Request body**:
     ```
     {"ref":"main"}
     ```
5. **Create / Save**

> 성공하면 응답코드 **204** 가 옵니다(정상). cron-job.org 의 실행 로그에서 204 면 OK.

---

## 3단계 — (선택) 자정 일일 그래프도 외부 크론으로

같은 방식으로 cronjob 하나 더 만들면 됩니다. URL 만 바꾸세요:
```
https://api.github.com/repos/mungiri/powerplanner/actions/workflows/daily-graph.yml/dispatches
```
- **Schedule**: 매일 **00:05** (cron-job.org 시간대를 Asia/Seoul 로 설정)
- 나머지(헤더·body)는 동일

---

## 확인

cron-job.org 가 처음 호출하면, repo **Actions** 탭에 새 실행이 뜨고 텔레그램으로 알림이 옵니다.
이후로는 cron-job.org 가 매시간 확실하게 깨웁니다.

> GitHub 워크플로우의 `schedule:` 줄은 남겨둬도 무방합니다(가끔 GitHub이 추가로 돌려도 무해).
> 외부 크론이 주 트리거가 됩니다.
