#!/bin/bash
# 맥 launchd / cron 에서 호출하는 실행 래퍼.
# venv 를 활성화하고 main.py 를 1회 실행한다.
cd "$(dirname "$0")" || exit 1

# 가상환경이 있으면 사용
if [ -d "venv" ]; then
  source venv/bin/activate
fi

python3 main.py --once >> run.log 2>&1
