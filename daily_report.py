"""하루치 시간대별 사용량 그래프를 텔레그램으로 전송.

자정 직후(매일 1회) 실행하면 '어제 하루'의 전체 24시간 그래프를 보낸다.

사용법:
    python daily_report.py             # 어제 날짜로 그래프 전송
    python daily_report.py 2026-06-21  # 특정 날짜 지정
"""
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

from scraper import fetch_hourly_usage
from graph import render_hourly
from notify import send_telegram_photo, send_telegram

KST = timezone(timedelta(hours=9))


def _yesterday_kst() -> str:
    return (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")


def _hourly_table(hours, usage) -> str:
    """24시간 사용량을 2단 표(monospace)로. 텔레그램 <pre> 안에 넣어 정렬."""
    n = len(hours)
    half = (n + 1) // 2
    rows = []
    for i in range(half):
        left = f"{hours[i]:>2}시 {usage[i]:>5.2f}"
        j = i + half
        right = f"{hours[j]:>2}시 {usage[j]:>5.2f}" if j < n else ""
        rows.append(f"{left}    {right}".rstrip())
    return "\n".join(rows)


def run(date_str: str) -> None:
    headless = os.getenv("HEADLESS", "true").lower() != "false"
    try:
        data = fetch_hourly_usage(date_str, headless=headless)
    except Exception as e:
        send_telegram(f"⚠️ 일일 그래프 조회 실패 ({date_str})\n{e}")
        raise

    png = render_hourly(data)

    usage = data["usage"]
    total = data["total"]
    prev_total = round(sum(data.get("prev_day") or []), 3)
    peak_i = max(range(len(usage)), key=lambda i: usage[i]) if usage else 0
    peak_hour = data["hours"][peak_i] if usage else "-"

    caption_lines = [
        f"📊 <b>{date_str} 하루 전력 사용량</b>",
        f"총 사용량: <b>{total:g} kWh</b>",
        f"최대 시간대: {peak_hour}시 ({usage[peak_i]:g} kWh)" if usage else "",
    ]
    if prev_total:
        diff = round(total - prev_total, 3)
        sign = "▲" if diff > 0 else "▼"
        caption_lines.append(f"전일 대비: {sign}{abs(diff):g} kWh (전일 {prev_total:g})")

    if usage:
        caption_lines.append("")
        caption_lines.append("⏱ <b>시간대별 (kWh)</b>")
        caption_lines.append("<pre>" + _hourly_table(data["hours"], usage) + "</pre>")

    caption = "\n".join([l for l in caption_lines if l])

    send_telegram_photo(png, caption)
    print(f"[{date_str}] 그래프 전송 완료: {png}")


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else _yesterday_kst()
    run(date)
