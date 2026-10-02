#!/bin/sh
# Запуск Goblin Voice (откроется окно). Прошлые запуски утилита убивает сама.
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$DIR/.venv/bin/python" ]; then
  echo "No Python environment yet. Run:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$DIR/logs"
cd "$DIR"
nohup "$DIR/.venv/bin/python" "$DIR/app.py" >> "$DIR/logs/stdout.log" 2>&1 &
echo "Goblin Voice started (pid $!)"
