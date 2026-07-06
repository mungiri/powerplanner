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

# pythonw.exe(작업 스케줄러)는 sys.stdout/err 가 None → print 크래시,
# cp949 콘솔은 한글 인코딩 실패 → 둘 다 방지. (main.py 와 동일)
_devnull = open(os.devnull, "w", encoding="utf-8")
for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name)
    if _s is None:
        setattr(sys, _name, _devnull)
    else:
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

load_dotenv()

from scraper import fetch_summary_and_hourly
from graph import render_hourly
from notify import send_telegram_photo, send_telegram

KST = timezone(timedelta(hours=9))


def _yesterday_kst() -> str:
    return (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")


def run(date_str: str) -> None:
    headless = os.getenv("HEADLESS", "true").lower() != "false"
    try:
        summary, data = fetch_summary_and_hourly(date_str, headless=headless)
    except Exception as e:
        import html
        send_telegram(f"⚠️ 일일 그래프 조회 실패 ({date_str})\n{html.escape(str(e))}")
        raise

    png = render_hourly(data)

    usage = data["usage"]
    total = data["total"]
    prev_total = round(sum(data.get("prev_day") or []), 3)
    peak_i = max(range(len(usage)), key=lambda i: usage[i]) if usage else 0
    peak_hour = data["hours"][peak_i] if usage else "-"

    # 하루 요금: 한전이 일일 요금은 안 줘서 누적 평균단가(누적요금÷누적사용량)로 환산
    cum_usage = summary.get("usage")
    cum_charge = summary.get("total_charge")
    rate = (cum_charge / cum_usage) if (cum_usage and cum_charge) else 0
    day_cost = round(total * rate)

    caption_lines = [
        f"📊 <b>{date_str} 하루 전력 사용량</b>",
        f"총 사용량: <b>{total:g} kWh / 약 {day_cost:,}원</b>",
        f"최대 시간대: {peak_hour}시 ({usage[peak_i]:g} kWh)" if usage else "",
    ]
    if prev_total:
        diff = round(total - prev_total, 3)
        sign = "▲" if diff > 0 else "▼"
        caption_lines.append(f"전일 대비: {sign}{abs(diff):g} kWh (전일 {prev_total:g})")
    caption = "\n".join([l for l in caption_lines if l])

    send_telegram_photo(png, caption)
    print(f"[{date_str}] 그래프 전송 완료: {png}")


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else _yesterday_kst()
    run(date)
