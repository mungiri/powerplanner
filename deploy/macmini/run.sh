#!/bin/bash
# launchd 에서 호출하는 실행 래퍼 (Mac Mini 24시간 상시 실행용).
#   사용: run.sh main.py         → 전기요금 알림
#        run.sh daily_report.py  → 어제 하루 그래프
#
# 이 스크립트 위치(deploy/macmini)를 기준으로 프로젝트 루트를 스스로 계산하므로
# 경로를 하드코딩하지 않는다. venv 의 파이썬으로 대상 스크립트를 실행하고 logs/ 에 기록.

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR" || exit 1

mkdir -p logs
LOG="logs/${1%.py}.log"

echo "===== $(date '+%F %T %Z') run $* =====" >> "$LOG"
"$PROJECT_DIR/venv/bin/python" "$@" >> "$LOG" 2>&1
