# 파워플래너 전기요금 자동 알림

한전 **파워플래너**에 자동 로그인해 우리집 전기요금을 가져와서 **텔레그램**으로 알려줍니다.
하루 4번(00:10 / 06:10 / 12:10 / 18:10) 자동 조회 + 매일 아침 6시 어제 하루 그래프.

---

## ⚠️ 반드시 한국 IP(로컬 PC)에서 실행

2026-07 부터 한전(pp.kepco.co.kr)이 **GitHub Actions 등 해외/데이터센터 IP 를 차단**합니다.
증상: 최초 접속(`page.goto`)이 응답 없이 30초 타임아웃 → `⚠️ 조회 실패 Timeout` 알림만 반복.

그래서 이 프로젝트는 **한국 IP 인 로컬 PC(Windows 작업 스케줄러)** 에서 돌립니다.

- `.github/workflows/*.yml` 은 **비활성(no-op)** 상태입니다. GitHub Actions 로는 조회가 불가능합니다.
- `run.sh`, `com.user.powerplanner.plist`(맥 launchd), `CRON_EXTERNAL.md`(cron-job.org) 는 **레거시**입니다.

---

## 동작 방식

- Playwright(헤드리스 크롬)로 파워플래너에 로그인 → 요금 숫자·시간대별 사용량 추출
- 직전 조회 이후의 **시간대별 사용량**을 모아 텔레그램으로 전송
- 한전 AMI 수집이 1~몇 시간 늦게 오므로, **실제로 채워진 데이터까지만** 보고하고
  `state.json` 에 마지막 보고 지점을 기록해 **다음 실행이 이어받아** 누락 없이 따라잡음
  (`main.py` 의 `_window_slots` / `last_slot_end`)

> 파워플래너는 공개 API가 없어 로그인 화면을 자동 조작합니다. 로그인 폼(`#RSA_USER_ID`/
> `#RSA_USER_PWD`/`#intro_btn_indi`)과 요금 요소(`#TOTAL_CHARGE` 등)는 실제 페이지로 확정.
> 비밀번호는 페이지 JS가 RSA로 암호화해 전송합니다. (구조가 바뀌면 아래 "셀렉터 튜닝" 참고)

---

## 설치 (Windows 기준)

```powershell
cd powerplanner

# 1) 가상환경 + 패키지
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2) Playwright 브라우저 — ★ 한글 없는 ASCII 경로에 설치 (아래 "주의점" 참고)
$env:PLAYWRIGHT_BROWSERS_PATH = "C:\pw-browsers"
python -m playwright install chromium

# 3) 설정 파일
copy .env.example .env
# .env 를 열어 한전 ID/PW, 텔레그램 토큰/챗ID 입력 + 아래 한 줄 추가:
#   PLAYWRIGHT_BROWSERS_PATH=C:\pw-browsers
```

### 텔레그램 봇 만들기
1. 텔레그램에서 **@BotFather** → `/newbot` → 토큰 발급 → `.env` 의 `TELEGRAM_BOT_TOKEN`
2. 만든 봇과 대화창을 열고 아무 메시지나 한 번 전송
3. `python get_chat_id.py` → 나온 `chat_id` 를 `.env` 의 `TELEGRAM_CHAT_ID` 에 입력

### 먼저 테스트
```powershell
venv\Scripts\Activate.ps1
python main.py                 # 1회 조회 → 텔레그램 알림
python daily_report.py         # 어제 하루 그래프 전송
```

---

## 자동 실행 (Windows 작업 스케줄러)

`pythonw.exe`(콘솔 없는 파이썬)로 아래 두 태스크를 등록합니다. PowerShell에서:

```powershell
$proj = (Get-Location).Path
$pyw  = Join-Path $proj "venv\Scripts\pythonw.exe"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# 1) 전기요금 알림 — 00:10 / 06:10 / 12:10 / 18:10
$trig = @(
  New-ScheduledTaskTrigger -Daily -At 00:10
  New-ScheduledTaskTrigger -Daily -At 06:10
  New-ScheduledTaskTrigger -Daily -At 12:10
  New-ScheduledTaskTrigger -Daily -At 18:10
)
Register-ScheduledTask -TaskName "PowerPlanner 전기요금 알림" `
  -Action (New-ScheduledTaskAction -Execute $pyw -Argument "main.py" -WorkingDirectory $proj) `
  -Trigger $trig -Settings $settings -Principal $principal

# 2) 일일그래프 — 매일 06:00 정각 (어제 하루 그래프)
Register-ScheduledTask -TaskName "PowerPlanner 일일그래프" `
  -Action (New-ScheduledTaskAction -Execute $pyw -Argument "daily_report.py" -WorkingDirectory $proj) `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 06:00) -Settings $settings -Principal $principal
```

### 전원/절전 동작
- `-StartWhenAvailable` : 예약 시각에 PC가 꺼져 있었으면 **다음에 켤 때 실행**(밀린 시간대는 `state.json` 이어받기로 backfill).
- `-WakeToRun` + 전원 옵션 "절전 타이머 허용" : **절전 상태면 깨어나서 실행**.
  ```powershell
  # 절전 타이머 허용(AC/DC 모두) — 이게 꺼져 있으면 WakeToRun 무시됨
  powercfg /SETACVALUEINDEX SCHEME_CURRENT 238C9FA8-0AAD-41ED-83F4-97BE242C8F20 BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D 1
  powercfg /SETDCVALUEINDEX SCHEME_CURRENT 238C9FA8-0AAD-41ED-83F4-97BE242C8F20 BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D 1
  powercfg /SETACTIVE SCHEME_CURRENT
  ```
- `-AllowStartIfOnBatteries` : **배터리(어댑터 미연결)에서도 실행**. 단 배터리가 거의 없으면 Windows가 깨우기를 건너뜀 → 다음에 catch-up.
- **완전 종료(전원 OFF)** 상태에서는 소프트웨어로 깨울 수 없음 → 다음 부팅 때 catch-up.

수동 실행/삭제:
```powershell
Start-ScheduledTask   -TaskName "PowerPlanner 전기요금 알림"   # 지금 한 번 실행
Unregister-ScheduledTask -TaskName "PowerPlanner 전기요금 알림" -Confirm:$false  # 삭제
```

---

## Windows 실행 시 주의점 (겪은 함정)

1. **`pythonw.exe` 는 `sys.stdout/err` 가 `None`** → 첫 `print` 에서 크래시(종료코드 1).
   → `main.py`/`daily_report.py` 상단에서 None 이면 devnull, 콘솔이면 UTF-8 로 고정 처리.
2. **경로에 한글(예: `C:\Users\장문길\...`) 이 있으면** 스케줄러 세션의 Playwright 가
   브라우저 exe 를 못 찾음("Executable doesn't exist"). 대화형 콘솔에서는 됨.
   → 브라우저를 **ASCII 경로 `C:\pw-browsers`** 에 설치하고 `.env` 의 `PLAYWRIGHT_BROWSERS_PATH` 로 지정.
3. **실패 알림 텔레그램은 `parse_mode=HTML`** → 에러 텍스트의 `<` (예: Playwright 배너 `<3`)가
   태그로 파싱돼 400. → 에러 텍스트를 `html.escape` 로 이스케이프.

문제 진단: 헤드리스라 stdout 을 볼 수 없으니, 미처리 예외는 `run_error.log` 에 traceback 이 남습니다.

---

## 셀렉터 튜닝 (요금이 안 잡힐 때만)

```powershell
python main.py --capture   # 브라우저 창이 뜨고 capture/ 에 화면·HTML 저장
```
`capture/*.html` 에서 요금 요소의 id/class 를 찾아 `pp_selectors.py` 를 수정합니다.

---

## 파일 구성

| 파일 | 역할 |
|------|------|
| `main.py` | 조회 → 시간대별 집계 → 알림 오케스트레이션 |
| `scraper.py` | Playwright 로그인 & 요금·시간대별 추출 |
| `pp_selectors.py` | 페이지 URL/셀렉터 (튜닝 지점) |
| `notify.py` | 텔레그램 전송(메시지/사진) |
| `daily_report.py` | 어제 하루 시간대별 그래프 생성·전송 |
| `graph.py` | matplotlib 막대그래프 렌더링 |
| `bot.py` | 텔레그램 명령(`/now`, `/graph`) 리스너 |
| `get_chat_id.py` | 텔레그램 chat_id 확인 도우미 |
| `state.json` | 직전 요금값·마지막 보고 시각 저장 (자동 생성) |
| `run_error.log` | 미처리 예외 traceback (자동 생성) |
| `.github/workflows/*.yml` | **레거시·비활성** (한전 해외 IP 차단으로 사용 불가) |
| `run.sh`, `com.user.powerplanner.plist` | **레거시** (맥 launchd용) |

## 텔레그램 명령 (`bot.py` 실행 중일 때)

- `/now` 또는 `요금` → 지금 요금 조회
- `/graph` 또는 `그래프` → 오늘 시간대별 사용량 그래프
