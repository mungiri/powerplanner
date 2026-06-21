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

from main import fetch_data, apply_state
from notify import send_telegram_to

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"

TRIGGERS = {"/now", "/요금", "요금", "지금", "조회"}
HELP = (
    "⚡ 파워플래너 요금봇\n"
    "/now (또는 '요금', '지금') 보내면 지금 바로 조회해서 알려드려요.\n"
    "매시간 자동 알림은 따로 돌아갑니다."
)


def handle(chat_id, text: str):
    text = (text or "").strip()
    if text in ("/start", "/help", "도움말"):
        send_telegram_to(chat_id, HELP)
        return
    if text.lower() in {t.lower() for t in TRIGGERS}:
        send_telegram_to(chat_id, "⏳ 조회 중이에요… (약 15초)")
        try:
            data = fetch_data()
            msg, _changed, _over = apply_state(data)
            send_telegram_to(chat_id, msg)
        except Exception as e:
            send_telegram_to(chat_id, f"⚠️ 조회 실패\n{e}")
    else:
        send_telegram_to(chat_id, "명령을 못 알아들었어요. /now 또는 '요금' 이라고 보내보세요.")


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
