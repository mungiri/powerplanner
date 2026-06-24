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

from scraper import login_and_fetch
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


def build_message(data: dict, prev_data, window_label: str = "직전 조회 이후") -> str:
    """알림 메시지 본문 생성.

    prev_data: 직전 조회 때 저장한 data dict (없으면 None).
    실시간요금·사용량은 '청구월 누적값'이라, 그 차이가 이번 구간(약 6시간) 사용분이다.
    """
    amount = data["total_charge"]
    lines = [f"⚡ <b>파워플래너 전기요금</b>  ({kst_now_str()})"]

    # 이번 구간(약 6시간) 동안 쓴 사용량 / 요금 = 누적값의 차이
    if prev_data:
        d_usage = round((data.get("usage") or 0) - (prev_data.get("usage") or 0), 3)
        d_charge = amount - (prev_data.get("total_charge") or 0)
        if d_usage >= 0 and d_charge >= 0:  # 월 초기화 시엔 음수 → 표시 생략
            lines.append(f"🔸 <b>{window_label}: {d_usage:g} kWh / {d_charge:,}원</b>")

    pc = data.get("predict_charge")
    lines.append(f"누적 실시간요금: {amount:,}원")
    if pc is not None:
        lines.append(f"예상요금(월말): {pc:,}원")
    if data.get("usage") is not None:
        lines.append(f"누적 사용량: {data['usage']}kWh")

    # 예상요금 3만원(WARN_THRESHOLD) 이상 경고
    if pc is not None and pc >= WARN_THRESHOLD:
        lines.append("")
        lines.append(f"🚨 <b>예상요금이 {WARN_THRESHOLD:,}원을 넘었습니다!</b>")

    return "\n".join(lines)


def fetch_data(capture: bool = False) -> dict:
    """로그인 후 요금 데이터를 조회한다 (상태 갱신·알림 없음)."""
    headless = os.getenv("HEADLESS", "true").lower() != "false"
    return login_and_fetch(headless=headless, capture=capture)


def apply_state(data: dict):
    """state 를 갱신하고 (메시지, 변동여부, 경고진입여부) 를 돌려준다."""
    state = _load_state()
    prev = state.get("amount")
    prev_data = state.get("data")
    prev_warned = state.get("warned", False)

    # 직전 조회로부터 경과 시간 → "지난 N시간" 라벨
    window_label = "직전 조회 이후"
    prev_iso = state.get("ts")
    now_dt = datetime.now(KST)
    if prev_iso:
        try:
            elapsed_h = (now_dt - datetime.fromisoformat(prev_iso)).total_seconds() / 3600
            if elapsed_h >= 0.5:
                window_label = f"지난 {round(elapsed_h)}시간"
        except Exception:
            pass

    pc = data.get("predict_charge")
    over = pc is not None and pc >= WARN_THRESHOLD

    msg = build_message(data, prev_data, window_label)

    state["amount"] = data["total_charge"]
    state["data"] = data
    state["warned"] = over
    state["updated_at"] = kst_now_str()
    state["ts"] = now_dt.isoformat()
    _save_state(state)

    changed = prev is None or prev != data["total_charge"]
    newly_over = over and not prev_warned  # 막 3만원을 넘긴 순간
    return msg, changed, newly_over


def run_once() -> None:
    change_only = os.getenv("NOTIFY_ON_CHANGE_ONLY", "true").lower() == "true"
    now = kst_now_str()

    try:
        data = fetch_data()
    except Exception as e:
        send_telegram(f"⚠️ 파워플래너 조회 실패 ({now})\n{e}")
        raise

    msg, changed, newly_over = apply_state(data)

    # 변동이 있거나(또는 always 모드), 막 3만원을 넘긴 경우 전송
    if (not change_only) or changed or newly_over:
        send_telegram(msg)
        print(f"[{now}] 알림 전송: {data['total_charge']:,}원")
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
