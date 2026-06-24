"""텔레그램 명령 리스너 — 원할 때 즉시 요금 조회.

실행:
    python bot.py        # 켜두면 텔레그램에서 명령에 반응

지원 명령(봇에게 보내면 됨):
    /now  /요금  요금  지금     → 지금 바로 조회해서 답장
    /start                      → 도움말

※ 이 스크립트가 켜져 있는 동안에만 명령에 반응합니다.
   (매시간 자동 알림은 GitHub Actions 가 따로 처리하므로 이 스크립트가 꺼져 있어도 동작)
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

from datetime import datetime, timezone, timedelta

from main import compose
from notify import send_telegram_to, send_telegram_photo
from scraper import fetch_hourly_usage
from graph import render_hourly

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"
KST = timezone(timedelta(hours=9))

NOW_TRIGGERS = {"/now", "/요금", "요금", "지금", "조회"}
GRAPH_TRIGGERS = {"/graph", "그래프", "/그래프", "사용량", "오늘그래프"}
HELP = (
    "⚡ 파워플래너 요금봇\n"
    "/now (또는 '요금') → 지금 요금 조회\n"
    "/graph (또는 '그래프') → 오늘 시간대별 사용량 그래프\n"
    "매시간 요금 알림·자정 일일그래프는 자동으로 따로 돌아갑니다."
)


def handle(chat_id, text: str):
    text = (text or "").strip()
    low = text.lower()
    if text in ("/start", "/help", "도움말"):
        send_telegram_to(chat_id, HELP)
    elif low in {t.lower() for t in NOW_TRIGGERS}:
        send_telegram_to(chat_id, "⏳ 요금 조회 중이에요… (약 15초)")
        try:
            # persist=False: 즉석 조회는 6시간 구간 기준점(ts)을 건드리지 않음
            msg, _changed, _over = compose(persist=False)
            send_telegram_to(chat_id, msg)
        except Exception as e:
            send_telegram_to(chat_id, f"⚠️ 조회 실패\n{e}")
    elif low in {t.lower() for t in GRAPH_TRIGGERS}:
        send_telegram_to(chat_id, "⏳ 오늘 사용량 그래프 그리는 중이에요…")
        try:
            today = datetime.now(KST).strftime("%Y-%m-%d")
            hd = fetch_hourly_usage(today)
            png = render_hourly(hd)
            send_telegram_photo(png, f"📊 오늘({today}) 시간대별 사용량 (현재까지 {hd['total']:g} kWh)", chat_id)
        except Exception as e:
            send_telegram_to(chat_id, f"⚠️ 그래프 실패\n{e}")
    else:
        send_telegram_to(chat_id, "명령을 못 알아들었어요. /now (요금) 또는 /graph (그래프) 를 보내보세요.")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN 이 .env 에 없습니다.")
    print("봇 리스너 시작. 텔레그램에서 /now 또는 '요금' 을 보내보세요. (Ctrl+C 종료)")

    # 시작 시점 이전의 묵은 메시지는 건너뛴다
    offset = None
    try:
        r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=20).json()
        if r.get("result"):
            offset = r["result"][-1]["update_id"] + 1
    except Exception:
        pass

    while True:
        try:
            params = {"timeout": 50}
            if offset is not None:
                params["offset"] = offset
            r = requests.get(f"{API}/getUpdates", params=params, timeout=60).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat = msg.get("chat", {})
                if chat.get("id"):
                    handle(chat["id"], msg.get("text", ""))
        except requests.exceptions.Timeout:
            continue
        except KeyboardInterrupt:
            print("\n종료")
            break
        except Exception as e:
            print("오류:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
