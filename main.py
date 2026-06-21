"""파워플래너 전기요금 자동 조회 → 텔레그램 알림.

사용법:
    python main.py            # 1회 조회 후 알림 (스케줄러가 1시간마다 호출하는 기본 모드)
    python main.py --capture  # 로그인 후 페이지를 capture/ 에 저장 (셀렉터 튜닝용)
    python main.py --loop     # 이 프로세스 안에서 1시간마다 반복 (스케줄러 대신 쓰고 싶을 때)
"""
import os
import sys
import json
import time
import argparse
import pathlib
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from scraper import login_and_fetch
from notify import send_telegram

STATE_FILE = pathlib.Path(__file__).parent / "state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_message(data: dict, prev) -> str:
    amount = data["total_charge"]
    lines = ["⚡ <b>파워플래너 전기요금</b>"]

    if prev is None or prev == amount:
        lines.append(f"실시간요금: <b>{amount:,}원</b>")
    else:
        diff = amount - prev
        sign = "▲" if diff > 0 else "▼"
        lines.append(f"실시간요금: <b>{amount:,}원</b> ({sign}{abs(diff):,}원)")

    if data.get("predict_charge") is not None:
        lines.append(f"예상요금: {data['predict_charge']:,}원")
    if data.get("usage") is not None:
        lines.append(f"사용량: {data['usage']}kWh (예상 {data.get('predict_usage')}kWh)")
    if data.get("period"):
        lines.append(f"청구기간: {data['period']}")
    if data.get("as_of"):
        lines.append(f"기준일: {data['as_of']}")
    return "\n".join(lines)


def run_once() -> None:
    headless = os.getenv("HEADLESS", "true").lower() != "false"
    change_only = os.getenv("NOTIFY_ON_CHANGE_ONLY", "true").lower() == "true"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        data = login_and_fetch(headless=headless, capture=False)
    except Exception as e:
        send_telegram(f"⚠️ 파워플래너 조회 실패 ({now})\n{e}")
        raise

    amount = data["total_charge"]
    state = _load_state()
    prev = state.get("amount")

    state["amount"] = amount
    state["data"] = data
    state["updated_at"] = now
    _save_state(state)

    if change_only and prev == amount:
        print(f"[{now}] 변동 없음: {amount:,}원 — 알림 생략")
        return

    send_telegram(_build_message(data, prev))
    print(f"[{now}] 알림 전송: {amount:,}원")


def run_capture() -> None:
    print("디버그 캡처 모드: 로그인 후 capture/ 에 스크린샷·HTML 저장")
    data = login_and_fetch(headless=False, capture=True)
    print(f"추출된 데이터: {data}")
    print("값이 비어있으면 capture/ 의 화면을 보고 로그인/셀렉터를 점검하세요.")


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
