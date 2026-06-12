#!/usr/bin/env bash
# macOS: decrementa el contador de sesiones (dicta se auto-cierra al llegar a 0).
DIR="$HOME/Library/Application Support/dicta"
COUNTER="$DIR/sessions.count"
n=0
[ -f "$COUNTER" ] && n=$(tr -d '[:space:]' < "$COUNTER")
[ -z "$n" ] && n=0
new=$((n - 1))
[ "$new" -lt 0 ] && new=0
echo "$new" > "$COUNTER"
