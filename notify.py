"""텔레그램 알림 전송 모듈."""
import os
import requests


def send_telegram_to(chat_id, text: str) -> None:
    """지정한 chat_id 로 메시지를 보낸다. 토큰/챗ID 미설정 시 콘솔 출력만."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
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


def send_telegram(text: str) -> None:
    """기본 수신자(.env 의 TELEGRAM_CHAT_ID)에게 보낸다."""
    send_telegram_to(os.getenv("TELEGRAM_CHAT_ID"), text)


def send_telegram_photo(photo_path: str, caption: str = "", chat_id=None) -> None:
    """사진(그래프 PNG)을 캡션과 함께 보낸다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[notify] 텔레그램 미설정 — 사진 전송 생략: {photo_path}")
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(photo_path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": f},
            timeout=60,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"텔레그램 사진 전송 실패 {resp.status_code}: {resp.text}")
