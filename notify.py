"""텔레그램 알림 전송 모듈."""
import os
import requests


def send_telegram(text: str) -> None:
    """텔레그램으로 메시지를 보낸다. 토큰/챗ID 미설정 시 조용히 콘솔 출력만 한다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[notify] 텔레그램 미설정 — 콘솔 출력만 합니다:\n" + text)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"텔레그램 전송 실패 {resp.status_code}: {resp.text}")
