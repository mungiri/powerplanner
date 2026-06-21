"""텔레그램 chat_id 확인 도우미.

1) @BotFather 에서 봇을 만들고 토큰을 받는다.
2) 그 봇과의 대화창에 아무 메시지나 하나 보낸다.
3) .env 의 TELEGRAM_BOT_TOKEN 을 채운 뒤 이 스크립트를 실행한다.
   → 출력되는 chat id 를 .env 의 TELEGRAM_CHAT_ID 에 넣는다.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    raise SystemExit("먼저 .env 에 TELEGRAM_BOT_TOKEN 을 설정하세요.")

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
data = resp.json()

if not data.get("ok"):
    raise SystemExit(f"API 오류: {data}")

results = data.get("result", [])
if not results:
    raise SystemExit("업데이트가 없습니다. 봇에게 메시지를 한 번 보낸 뒤 다시 실행하세요.")

seen = {}
for upd in results:
    msg = upd.get("message") or upd.get("channel_post") or {}
    chat = msg.get("chat", {})
    if chat.get("id"):
        seen[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name", "")

print("발견된 chat:")
for cid, name in seen.items():
    print(f"  chat_id = {cid}   ({name})")
print("\n위 chat_id 를 .env 의 TELEGRAM_CHAT_ID 에 넣으세요.")
