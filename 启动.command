#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo '请先按 README.md 安装运行依赖。'; read; exit 1
fi
if [[ ! -f frontend/dist/index.html ]]; then
  echo '请先运行 npm --prefix frontend ci && npm --prefix frontend run build'; read; exit 1
fi
if curl -fsS http://127.0.0.1:8765/api/v1/health >/dev/null 2>&1; then
  open 'http://127.0.0.1:8765'; exit 0
fi
(sleep 2; open 'http://127.0.0.1:8765') &
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
