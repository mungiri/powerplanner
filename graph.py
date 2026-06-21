"""시간대별 사용량을 막대그래프 PNG 로 렌더링한다.

이미지 안의 글자는 영문/숫자만 사용한다 (서버에 한글 폰트가 없어도 안 깨지게).
"""
import pathlib

import matplotlib
matplotlib.use("Agg")  # 디스플레이 없는 서버용
import matplotlib.pyplot as plt

OUT_DIR = pathlib.Path(__file__).parent / "out"


def render_hourly(data: dict) -> str:
    """fetch_hourly_usage 결과 dict 를 받아 PNG 를 만들고 경로를 반환."""
    OUT_DIR.mkdir(exist_ok=True)
    hours = data["hours"]
    usage = data["usage"]
    prev = data.get("prev_day") or []
    date = data["date"]
    total = data["total"]

    x = list(range(len(hours)))
    fig, ax = plt.subplots(figsize=(11, 4.5))

    # 오늘 사용량 (막대)
    ax.bar([i - 0.2 for i in x], usage, width=0.4, color="#fd8601", label="This day")
    # 전일 동시간 (비교 막대)
    if prev and any(prev):
        ax.bar([i + 0.2 for i in x], prev, width=0.4, color="#bbbbbb", label="Prev day")

    # 최대 사용 시간 강조
    if usage:
        peak_i = max(range(len(usage)), key=lambda i: usage[i])
        ax.annotate(
            f"peak {usage[peak_i]:.2f}",
            xy=(peak_i - 0.2, usage[peak_i]),
            xytext=(0, 6), textcoords="offset points",
            ha="center", fontsize=8, color="#c0392b",
        )

    ax.set_title(f"Hourly Usage  {date}   (total {total:g} kWh)", fontsize=13)
    ax.set_xlabel("Hour")
    ax.set_ylabel("kWh")
    ax.set_xticks(x)
    ax.set_xticklabels([str(h) for h in hours], fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()

    out = OUT_DIR / f"usage_{date}.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return str(out)
