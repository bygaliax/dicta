#!/usr/bin/env bash
# macOS: incrementa el contador de sesiones de Claude Code y lanza dicta si no corre.
set -e
DIR="$HOME/Library/Application Support/dicta"
mkdir -p "$DIR"

COUNTER="$DIR/sessions.count"
n=0
[ -f "$COUNTER" ] && n=$(tr -d '[:space:]' < "$COUNTER")
[ -z "$n" ] && n=0
echo $((n + 1)) > "$COUNTER"

PIDFILE="$DIR/dicta.pid"
running=0
if [ -f "$PIDFILE" ]; then
  pid=$(tr -d '[:space:]' < "$PIDFILE")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then running=1; fi
fi

if [ "$running" -eq 0 ]; then
  # AJUSTAR: ruta real del clon de dicta
  REPO="$HOME/Desktop/InProgress/dicta"
  PY="$REPO/.venv/bin/python"
  nohup "$PY" -m dicta >/dev/null 2>&1 &
fi
