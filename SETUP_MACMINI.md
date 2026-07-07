# Mac Mini 24시간 상시 실행 세팅 가이드

> **이 문서를 읽는 대상: Mac Mini 에서 실행되는 Claude Code(또는 사람).**
> GitHub 의 이 저장소를 클론한 뒤, 아래 순서대로 실행하면 전기요금 알림이 24시간 자동으로 돕니다.
> 명령은 그대로 복사해 실행할 수 있게 작성되어 있습니다. 각 단계의 **검증(✅)** 을 반드시 확인하세요.

---

## 배경 (왜 Mac Mini 인가)

한전 파워플래너(pp.kepco.co.kr)는 2026-07 부터 **GitHub Actions 등 해외/데이터센터 IP 를 차단**합니다.
(증상: 최초 접속이 응답 없이 30초 타임아웃) 그래서 **한국 IP 에서 상시 실행**해야 하는데,
24시간 켜져 있는 **Mac Mini(한국 가정 IP)** 가 이 용도에 가장 적합합니다.

- 실행 주체: macOS `launchd` (스케줄러). 크론 대신 launchd 를 씁니다(맥 표준).
- 노트북(Windows)에서 겪던 절전-깨우기 문제가 **없습니다**(Mac Mini 는 상시 가동).

---

## 0. 사전 확인 (필수)

### 0-1. 한국 IP 에서 한전에 접속되는지 확인
```bash
curl -I --max-time 30 https://pp.kepco.co.kr/intro.do
```
✅ `HTTP/... 200` 이 나와야 합니다.
❌ 타임아웃/거부되면 이 Mac 의 IP 도 차단된 것 → 한국 가정용 회선인지 확인(VPN/회사망/클라우드면 안 됨).

### 0-2. 시스템 시간대가 한국인지 확인 (스케줄 시각이 KST 기준이므로)
```bash
date            # KST 여야 함
sudo systemsetup -gettimezone   # Asia/Seoul 확인 (아니면: sudo systemsetup -settimezone Asia/Seoul)
```

### 0-3. 필요한 것
- `git`, `python3`(3.10 이상 권장). 없으면 Homebrew 로: `brew install git python`
- **사람이 제공해야 하는 비밀값 4개** (아래 3단계에서 입력):
  `KEPCO_ID`, `KEPCO_PW`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  → 이 값들은 저장소에 없습니다(비밀). 사용자에게 요청하세요.

---

## 1. 클론

```bash
# 설치 위치 예시 (원하는 곳으로 변경 가능)
git clone https://github.com/mungiri/powerplanner.git ~/powerplanner
cd ~/powerplanner

# 이후 명령에서 쓸 프로젝트 경로 변수
export PROJECT_DIR="$HOME/powerplanner"
```
✅ `ls "$PROJECT_DIR/main.py"` 가 보이면 OK.

---

## 2. 파이썬 환경 + Playwright 브라우저

```bash
cd "$PROJECT_DIR"
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt

# Playwright 크로미움 (헤드리스). 맥은 홈 경로가 ASCII 라 별도 경로 지정 불필요.
./venv/bin/python -m playwright install chromium
```
✅ 에러 없이 끝나야 합니다. (맥에서 시스템 의존성 경고가 나오면 대개 무시 가능)

---

## 3. 설정 파일 `.env`

```bash
cd "$PROJECT_DIR"
cp .env.example .env
```

`.env` 를 열어 아래를 채웁니다. **비밀값 4개는 사용자에게 받아 입력**하세요:

```
KEPCO_ID=<한전 아이디>
KEPCO_PW=<한전 비밀번호>
TELEGRAM_BOT_TOKEN=<봇 토큰>
TELEGRAM_CHAT_ID=<채팅 ID>

# ↓ 매 예약 시각마다 무조건 알림 (요금 변동과 무관하게). 반드시 false.
NOTIFY_ON_CHANGE_ONLY=false
WARN_THRESHOLD=30000
HEADLESS=true
```

> `TELEGRAM_CHAT_ID` 를 모르면: 봇과 대화창에서 아무 메시지나 보낸 뒤
> `./venv/bin/python get_chat_id.py` 실행 → 나온 숫자를 입력.

✅ `.env` 는 `.gitignore` 에 있어 커밋되지 않습니다(비밀 유지). 확인: `git check-ignore .env` → `.env` 출력.

---

## 4. 수동 테스트 (스케줄 등록 전 반드시)

```bash
cd "$PROJECT_DIR"
./venv/bin/python main.py            # 전기요금 알림 1회
./venv/bin/python daily_report.py    # 어제 하루 그래프 1회
```
✅ **텔레그램에 실제로 메시지/사진이 도착**해야 합니다.
❌ `조회 실패 Timeout` → 0-1 의 IP 문제. ❌ 브라우저 못 찾음 → 2단계 `playwright install chromium` 재실행.

---

## 5. launchd 스케줄 등록

저장소의 템플릿(`deploy/macmini/*.plist`)에서 `__PROJECT_DIR__` 를 실제 경로로 치환해
`~/Library/LaunchAgents/` 에 설치합니다.

```bash
cd "$PROJECT_DIR"
chmod +x deploy/macmini/run.sh
mkdir -p logs ~/Library/LaunchAgents

for name in alert daily; do
  sed "s#__PROJECT_DIR__#$PROJECT_DIR#g" \
      "deploy/macmini/com.powerplanner.$name.plist" \
      > "$HOME/Library/LaunchAgents/com.powerplanner.$name.plist"
done

# 로드 (기존에 있으면 먼저 언로드)
for name in alert daily; do
  plist="$HOME/Library/LaunchAgents/com.powerplanner.$name.plist"
  launchctl unload "$plist" 2>/dev/null
  launchctl load -w "$plist"
done
```

> 최신 macOS(Ventura+)에서 `load` 대신 최신 명령을 쓰려면:
> `launchctl bootstrap gui/$(id -u) <plist>` / 해제 `launchctl bootout gui/$(id -u)/com.powerplanner.alert`

✅ 등록 확인:
```bash
launchctl list | grep powerplanner
```
→ `com.powerplanner.alert` 와 `com.powerplanner.daily` 두 줄이 보여야 합니다.

---

## 6. 즉시 실행해서 최종 검증

스케줄을 기다리지 말고 지금 강제로 한 번 돌려 봅니다.
```bash
# 최신 macOS
launchctl kickstart -k gui/$(id -u)/com.powerplanner.alert
# (구버전이면) launchctl start com.powerplanner.alert

sleep 90
tail -n 30 "$PROJECT_DIR/logs/main.log"
```
✅ 로그 끝에 `[YYYY.MM.DD ...] 알림 전송` 이 보이고 텔레그램이 오면 완료.

---

## 7. 절전 방지 (권장)

Mac Mini 가 절전에 들어가면 launchd 실행이 밀릴 수 있습니다. 상시 서버로 쓸 거면 잠자기 해제:
```bash
sudo pmset -a sleep 0 disksleep 0
sudo pmset -g            # sleep 0 확인
```
> launchd 는 절전이었어도 깨어난 직후 놓친 작업을 실행하고, `main.py` 는 밀린 시간대를
> `state.json` 이어받기로 backfill 하므로 데이터는 빠지지 않습니다. 그래도 정시 실행엔 잠자기 해제 권장.

---

## 문제 해결

| 증상 | 원인 / 조치 |
|------|------|
| `조회 실패 Timeout` | 한전이 이 IP 차단. 한국 가정용 회선인지 확인(0-1). VPN/클라우드면 불가. |
| `BrowserType.launch: Executable doesn't exist` | `./venv/bin/python -m playwright install chromium` 재실행 |
| 텔레그램 400 `can't parse entities` | 코드에서 이미 `html.escape` 처리됨. 최신 코드인지 `git pull` |
| launchd 가 안 뜸 | `launchctl list \| grep powerplanner` 비어 있으면 5단계 재실행. 경로에 공백/한글 없는지 확인 |
| 로그가 안 쌓임 | `logs/` 폴더 권한, plist 의 `__PROJECT_DIR__` 치환이 됐는지 확인(`cat ~/Library/LaunchAgents/com.powerplanner.alert.plist`) |

로그 위치:
- `logs/main.log`, `logs/daily_report.log` — 스크립트 출력
- `logs/launchd.alert.log`, `logs/launchd.daily.log` — launchd 레벨 출력
- `run_error.log` — 미처리 예외 traceback (있으면)

---

## 제거 (원상복구)

```bash
for name in alert daily; do
  plist="$HOME/Library/LaunchAgents/com.powerplanner.$name.plist"
  launchctl unload "$plist" 2>/dev/null
  rm -f "$plist"
done
launchctl list | grep powerplanner   # 아무것도 안 나오면 제거 완료
```

---

## 참고

- 스케줄 시각: 전기요금 알림 **00:10 / 06:10 / 12:10 / 18:10**, 일일그래프 **06:00** (모두 KST).
  바꾸려면 `deploy/macmini/*.plist` 의 `StartCalendarInterval` 수정 후 5단계 재등록.
- GitHub Actions 워크플로(`.github/workflows/*.yml`)는 **비활성(no-op)** 이며 Mac Mini 실행과 무관합니다.
- Windows 로컬 실행 방법은 `README.md` 참고(이 프로젝트는 원래 Windows 작업 스케줄러로도 돌아갑니다).
