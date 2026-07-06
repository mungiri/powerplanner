"""파워플래너 전기요금 자동 조회 → 텔레그램 알림.

사용법:
    python main.py            # 1회 조회 후 알림 (스케줄러가 매시간 호출하는 기본 모드)
    python main.py --capture  # 로그인 후 페이지를 capture/ 에 저장 (디버그용)
    python main.py --loop     # 이 프로세스 안에서 1시간마다 반복
"""
import os
import sys
import json
import time
import argparse
import pathlib
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

# 콘솔 환경 차이로 print 가 죽는 걸 방지:
#  - pythonw.exe(작업 스케줄러): sys.stdout/err 가 None → print 가 크래시
#  - cp949 콘솔: 한글/em대시(—) 인코딩 실패 → UnicodeEncodeError
# None 이면 devnull 로 대체, 있으면 UTF-8 로 고정한다.
_devnull = open(os.devnull, "w", encoding="utf-8")
if sys.stdout is None:
    sys.stdout = _devnull
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is None:
    sys.stderr = _devnull
else:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from scraper import login_and_fetch, fetch_summary_and_hourly_dates
from notify import send_telegram

STATE_FILE = pathlib.Path(__file__).parent / "state.json"

# 예상요금이 이 금액(원) 이상이면 경고 메시지 추가
WARN_THRESHOLD = int(os.getenv("WARN_THRESHOLD", "30000"))

# 한국 표준시 (UTC+9) — GitHub Actions(UTC)에서도 한국 시간으로 표시
KST = timezone(timedelta(hours=9))


def kst_now_str() -> str:
    """'2026.06.21 오후 07시' 형식의 현재 한국시각."""
    now = datetime.now(KST)
    ampm = "오전" if now.hour < 12 else "오후"
    h12 = now.hour % 12 or 12
    return f"{now.strftime('%Y.%m.%d')} {ampm} {h12:02d}시"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_message(data: dict, prev_data, window_label="직전 조회 이후", breakdown=None) -> str:
    """알림 메시지 본문 생성.

    prev_data: 직전 조회 때 저장한 data dict (없으면 None).
    breakdown: 이번 구간의 [(시각, kWh), ...] 시간대별 내역.
    실시간요금·사용량은 '청구월 누적값'이라, 그 차이가 이번 구간 사용분이다.
    """
    amount = data["total_charge"]
    pc = data.get("predict_charge")
    usage = data.get("usage")
    # 한전 차트 API는 시간당 kWh만 주고 요금(원)은 안 줘서, 누적 평균단가로 환산한다.
    rate = (amount / usage) if (usage and usage > 0) else 0

    lines = [f"🏡💡 <b>우리집 전기요금</b>  ({kst_now_str()})"]

    # 1) 지난 N시간 — 구간 합계 사용량 / 요금
    if breakdown:
        w_kwh = round(sum(u for _, u in breakdown), 3)
        w_won = round(w_kwh * rate)
        lines.append(f"🐣 <b>{window_label}: {w_kwh:g} kWh / {w_won:,}원</b>")
    elif prev_data:
        d_usage = round((usage or 0) - (prev_data.get("usage") or 0), 3)
        d_charge = amount - (prev_data.get("total_charge") or 0)
        if d_usage >= 0 and d_charge >= 0:
            lines.append(f"🐣 <b>{window_label}: {d_usage:g} kWh / {d_charge:,}원</b>")

    # 2) 누적 (한 줄, 슬래시 구분)  3) 예상요금(월말)
    if usage is not None:
        lines.append(f"💰 누적: {usage:g} kWh / {amount:,}원")
    else:
        lines.append(f"💰 누적 실시간요금: {amount:,}원")
    if pc is not None:
        lines.append(f"🔮 예상요금(월말): {pc:,}원")

    # 4) 이번 구간 시간대별 (kWh / 원)
    if breakdown:
        lines.append("")
        lines.append("⏰ <b>시간대별 사용량</b>")
        for hour, u in breakdown:
            lines.append(f"  ⤷ {hour}시: {u:g} kWh / {round(u * rate):,}원")

    # 예상요금 3만원(WARN_THRESHOLD) 이상 경고
    if pc is not None and pc >= WARN_THRESHOLD:
        lines.append("")
        lines.append(f"🚨 <b>예상요금이 {WARN_THRESHOLD:,}원을 넘었어요!</b>")

    return "\n".join(lines)


def _window_slots(prev_dt: datetime, now_dt: datetime):
    """prev_dt~now_dt 사이의 '완료된 1시간 슬롯'을 (날짜, 시각라벨) 목록으로.

    시각라벨은 차트의 MR_HHMI2 와 동일(끝시각, 1~24). 자정(00:00)은 전날의 24시.
    """
    slots = []
    e = now_dt.replace(minute=0, second=0, microsecond=0)  # 마지막 정시 경계
    start = prev_dt.replace(minute=0, second=0, microsecond=0)
    cur = start + timedelta(hours=1)
    guard = 0
    while cur <= e and guard < 48:
        guard += 1
        if cur.hour == 0:  # 자정 경계 = 전날 24시 슬롯
            d = (cur - timedelta(days=1)).strftime("%Y-%m-%d")
            label = 24
        else:
            d = cur.strftime("%Y-%m-%d")
            label = cur.hour
        slots.append((d, label))
        cur += timedelta(hours=1)
    return slots


def compose(persist: bool = True):
    """로그인→요약+이번 구간 시간대별 내역 수집→메시지 생성.

    persist=True 면 state(누적값·ts) 를 갱신한다.
    반환: (메시지, 변동여부, 경고진입여부)
    """
    headless = os.getenv("HEADLESS", "true").lower() != "false"

    state = _load_state()
    prev = state.get("amount")
    prev_data = state.get("data")
    prev_warned = state.get("warned", False)
    prev_iso = state.get("ts")

    now_dt = datetime.now(KST)
    today = now_dt.strftime("%Y-%m-%d")

    # 윈도우 시작점 = 마지막으로 '실제 보고한' 슬롯의 끝 시각.
    # 벽시계(now-N시간)가 아니라 보고 지점을 기준으로 이어가야,
    # AMI 지연으로 비어 있던 칸이 나중에 채워졌을 때 누락 없이 따라잡는다.
    last_iso = state.get("last_slot_end") or prev_iso
    last_end = None
    if last_iso:
        try:
            last_end = datetime.fromisoformat(last_iso)
        except Exception:
            last_end = None
    if last_end is None:
        last_end = now_dt - timedelta(hours=6)

    # 후보 슬롯: 마지막 보고 이후 ~ 지금까지의 '완료된' 1시간 칸.
    # 한전 AMI는 1~몇 시간 늦게 도착하므로, 끝쪽 미수집 칸은 아래에서 잘라낸다.
    slots = _window_slots(last_end, now_dt)

    # 필요한 모든 날짜(오늘 + 자정처럼 전날까지)를 로그인 1회로 조회 → 두 번째 로그인 실패로
    # 자정 시간대별이 통째로 비는 문제 방지.
    needed_dates = [today] + [d for d, _ in slots]
    data, hourly_by_date = fetch_summary_and_hourly_dates(needed_dates, headless=headless)

    # 슬롯별 사용량 채우기 (차트에 행이 없으면 None).
    filled = []
    for d, label in slots:
        hd = hourly_by_date.get(d) or {"hours": [], "usage": []}
        umap = dict(zip(hd["hours"], hd["usage"]))
        filled.append((d, label, umap.get(label)))

    # 꼬리에서 '아직 안 들어온' 칸(누락·0) 제거 → 5시 0kwh 같은 빈칸 표기 방지.
    # 가정용은 기저부하가 있어 실제 0 kWh 시간은 사실상 없음 → 끝쪽 0/누락=미수집으로 본다.
    while filled and (filled[-1][2] is None or filled[-1][2] <= 0):
        filled.pop()

    breakdown = [(label, u if u is not None else 0) for _, label, u in filled]

    n = len(breakdown)
    window_label = f"지난 {n}시간" if n else "직전 조회 이후"

    msg = build_message(data, prev_data, window_label, breakdown)

    pc = data.get("predict_charge")
    over = pc is not None and pc >= WARN_THRESHOLD
    if persist:
        state["amount"] = data["total_charge"]
        state["data"] = data
        state["warned"] = over
        state["updated_at"] = kst_now_str()
        state["ts"] = now_dt.isoformat()
        # 이번에 실제로 보고한 마지막 슬롯의 끝 시각을 기억 → 다음 실행이 이어받음.
        # (이번에 새로 보낸 게 없으면 기존 값 유지 = 다음에 같은 칸 재시도)
        if filled:
            d, label, _ = filled[-1]
            end_dt = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(hours=label)
            state["last_slot_end"] = end_dt.isoformat()
        _save_state(state)

    changed = prev is None or prev != data["total_charge"]
    newly_over = over and not prev_warned
    return msg, changed, newly_over


def run_once() -> None:
    change_only = os.getenv("NOTIFY_ON_CHANGE_ONLY", "true").lower() == "true"
    now = kst_now_str()

    try:
        msg, changed, newly_over = compose(persist=True)
    except Exception as e:
        # 에러 텍스트에 '<' 등이 있으면(예: Playwright 배너의 '<3') HTML 파싱 400 이 나므로 이스케이프.
        import html
        send_telegram(f"⚠️ 파워플래너 조회 실패 ({now})\n{html.escape(str(e))}")
        raise

    # 변동이 있거나(또는 always 모드), 막 3만원을 넘긴 경우 전송
    if (not change_only) or changed or newly_over:
        send_telegram(msg)
        print(f"[{now}] 알림 전송")
    else:
        print(f"[{now}] 변동 없음 — 알림 생략")


def run_capture() -> None:
    print("디버그 캡처 모드: 로그인 후 capture/ 에 스크린샷·HTML 저장")
    data = login_and_fetch(headless=False, capture=True)
    print(f"추출된 데이터: {data}")


def run_loop(interval_sec: int = 3600) -> None:
    print(f"루프 모드 시작: {interval_sec}초마다 조회 (Ctrl+C 로 종료)")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"오류: {e}", file=sys.stderr)
        time.sleep(interval_sec)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true", help="셀렉터 튜닝용 페이지 캡처")
    ap.add_argument("--loop", action="store_true", help="이 프로세스에서 1시간마다 반복")
    ap.add_argument("--once", action="store_true", help="1회 실행 (기본값)")
    args = ap.parse_args()

    try:
        if args.capture:
            run_capture()
        elif args.loop:
            run_loop()
        else:
            run_once()
    except Exception:
        # 헤드리스 스케줄(pythonw)에선 stdout/err 를 볼 수 없으니 파일로 traceback 남김.
        import traceback
        log = pathlib.Path(__file__).parent / "run_error.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now(KST).isoformat()} ===\n")
            traceback.print_exc(file=f)
        raise
