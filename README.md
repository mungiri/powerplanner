# 파워플래너 전기요금 자동 알림

한전 **파워플래너**에 자동 로그인해 우리집 전기요금을 가져와서 **텔레그램**으로 알려줍니다.
1시간마다 자동 실행 + 원할 때 수동 실행.

---

## 동작 방식

- Playwright(헤드리스 크롬)로 파워플래너에 로그인 → 요금 숫자 추출
- 직전 값과 비교해서 **값이 바뀌었을 때만** 텔레그램 알림 (옵션으로 매번 알림 가능)
- 맥 `launchd` 가 1시간마다 `run.sh` 호출

> 파워플래너는 공개 API가 없어 로그인 화면을 자동 조작하는 방식입니다.
> 로그인 폼(`#RSA_USER_ID`/`#RSA_USER_PWD`/`#intro_btn_indi`)과 요금 요소(`#TOTAL_CHARGE` 등)는
> 실제 페이지로 확정해 두었습니다. 비밀번호는 페이지 자체 JS가 RSA로 암호화해 전송합니다.
> (한전이 페이지 구조를 바꾸면 아래 4번 캡처로 다시 맞추면 됩니다.)

---

## 설치 (맥 기준)

```bash
cd powerplanner

# 1) 가상환경 + 패키지
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # 브라우저 엔진 설치 (최초 1회)

# 2) 설정 파일
cp .env.example .env
# .env 를 열어 한전 ID/PW, 텔레그램 토큰/챗ID 입력
```

### 텔레그램 봇 만들기
1. 텔레그램에서 **@BotFather** 검색 → `/newbot` → 토큰 발급 → `.env` 의 `TELEGRAM_BOT_TOKEN`
2. 만든 봇과 대화창을 열고 아무 메시지나 한 번 전송
3. `python3 get_chat_id.py` 실행 → 나온 `chat_id` 를 `.env` 의 `TELEGRAM_CHAT_ID` 에 입력

---

## 3) 먼저 테스트

```bash
source venv/bin/activate
python3 main.py            # 1회 조회 → 텔레그램 알림
```

## 4) 셀렉터 튜닝 (요금이 안 잡힐 때만)

요금이 `None` 으로 나오거나 로그인 칸을 못 찾으면:

```bash
python3 main.py --capture   # 브라우저 창이 뜨고 capture/ 에 화면·HTML 저장
```

`capture/*.html` 을 열어 **요금 숫자가 들어있는 요소의 id/class** 를 찾고,
`pp_selectors.py` 의 `BILL_AMOUNT_SELECTORS`(필요하면 `LOGIN_URL`, `ID_SELECTORS` 등)를 수정합니다.

---

## 5) 1시간마다 자동 실행 (launchd)

```bash
# com.user.powerplanner.plist 안의 __PROJECT_DIR__ 2곳을 실제 경로로 변경
#   예: /Users/내이름/powerplanner

cp com.user.powerplanner.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.powerplanner.plist
```

해제:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.powerplanner.plist
```

> launchd 는 맥이 절전이면 깨어난 직후 실행됩니다. PC가 켜져 있어야 동작합니다.

---

## 원할 때 수동 실행

```bash
source venv/bin/activate
python3 main.py
```

## 파일 구성

| 파일 | 역할 |
|------|------|
| `main.py` | 조회 → 비교 → 알림 오케스트레이션 |
| `scraper.py` | Playwright 로그인 & 요금 추출 |
| `pp_selectors.py` | 페이지 셀렉터 (튜닝 지점) |
| `notify.py` | 텔레그램 전송 |
| `get_chat_id.py` | 텔레그램 chat_id 확인 도우미 |
| `run.sh` | 스케줄러용 실행 래퍼 |
| `com.user.powerplanner.plist` | 맥 launchd (1시간 주기) |
| `state.json` | 직전 요금 값 저장 (자동 생성) |
| `daily_report.py` | 하루 시간대별 사용량 그래프 생성·전송 (자정 자동) |
| `graph.py` | matplotlib 막대그래프 렌더링 |
| `bot.py` | 텔레그램 명령(`/now`, `/graph`) 리스너 |

## 일일 그래프 (자정 자동)

매일 자정 직후 GitHub Actions(`daily-graph.yml`, 00:05 KST)가 **어제 하루 24시간 사용량 그래프**를 텔레그램으로 보냅니다.
수동: Actions → "파워플래너 일일 사용량 그래프" → Run workflow (날짜 입력 가능).
로컬: `python daily_report.py [YYYY-MM-DD]`

## 텔레그램 명령 (`bot.py` 실행 중일 때)

- `/now` 또는 `요금` → 지금 요금 조회
- `/graph` 또는 `그래프` → 오늘 시간대별 사용량 그래프
