#!/bin/sh
# Остановка Goblin Voice и его whisper-server
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# только процессы Python, у которых скрипт — наш app.py
our_pids() {
  ps -axo pid=,command= | awk -v app="$DIR/app.py" 'tolower($2) ~ /python/ && $3 == app {print $1}'
}

PIDS=$(our_pids)
if [ -n "$PIDS" ]; then
  kill $PIDS 2>/dev/null

  # пока открыто окно, утилита может не заметить сигнал: ждём до 2 с и добиваем
  for i in 1 2 3 4 5 6 7 8; do
    [ -z "$(our_pids)" ] && break
    sleep 0.25
  done
  LEFT=$(our_pids)
  [ -n "$LEFT" ] && kill -9 $LEFT 2>/dev/null
fi
rm -f logs/app.pid

# порт Whisper — из своих настроек, а если их ещё нет — из настроек по умолчанию
CONFIG=config.json
[ -f "$CONFIG" ] || CONFIG=config.default.json
PORT=$(python3 -c "import json; print(json.load(open('$CONFIG'))['whisper_port'])")
pkill -f "whisper-server.*--port $PORT" 2>/dev/null
echo "Goblin Voice stopped"
