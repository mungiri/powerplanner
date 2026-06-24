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

load_dotenv()

from scraper import login_and_fetch, fetch_hourly_usage, fetch_summary_and_hourly
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
    prev_dt = None
    if prev_iso:
        try:
            prev_dt = datetime.fromisoformat(prev_iso)
        except Exception:
            prev_dt = None
    if prev_dt is None:
        prev_dt = now_dt - timedelta(hours=6)

    today = now_dt.strftime("%Y-%m-%d")
    data, hourly_today = fetch_summary_and_hourly(today, headless=headless)

    # 이번 구간의 시간대별 내역 모으기 (필요한 날짜만 추가 조회)
    hourly_by_date = {today: hourly_today}
    breakdown = []
    for d, label in _window_slots(prev_dt, now_dt):
        if d not in hourly_by_date:
            try:
                hourly_by_date[d] = fetch_hourly_usage(d, headless=headless)
            except Exception:
                hourly_by_date[d] = {"hours": [], "usage": []}
        umap = dict(zip(hourly_by_date[d]["hours"], hourly_by_date[d]["usage"]))
        if label in umap:
            breakdown.append((label, umap[label]))

    elapsed_h = (now_dt - prev_dt).total_seconds() / 3600
    window_label = f"지난 {round(elapsed_h)}시간" if elapsed_h >= 0.5 else "직전 조회 이후"

    msg = build_message(data, prev_data, window_label, breakdown)

    pc = data.get("predict_charge")
    over = pc is not None and pc >= WARN_THRESHOLD
    if persist:
        state["amount"] = data["total_charge"]
        state["data"] = data
        state["warned"] = over
        state["updated_at"] = kst_now_str()
        state["ts"] = now_dt.isoformat()
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
        send_telegram(f"⚠️ 파워플래너 조회 실패 ({now})\n{e}")
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

    if args.capture:
        run_capture()
    elif args.loop:
        run_loop()
    else:
        run_once()
