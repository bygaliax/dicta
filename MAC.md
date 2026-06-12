# dicta en macOS

Port de dicta (originalmente Windows) a macOS. Mismo flujo: dictas por voz y el
texto aparece en el prompt de Claude Code. Whisper corre **local** (CPU en Mac —
faster-whisper no usa Metal/GPU).

## Qué cambió respecto a Windows
| Pieza | Windows | macOS |
|---|---|---|
| Config | `%APPDATA%\dicta` | `~/Library/Application Support/dicta` |
| Whisper | CUDA float16 | **CPU int8** (usa `model = "small"` o `"medium"` para ir más rápido) |
| Pegar texto | win32 + Ctrl+V | `pbcopy`/`pbpaste` + **Cmd+V** (pynput) |
| App frontal | win32gui HWND | AppKit `NSWorkspace` (PID) |
| Sonidos | winsound.Beep | `osascript beep` |
| Instancia única | mutex win32 | pidfile + `kill -0` |
| Hooks | PowerShell `.ps1` | shell `.sh` |
| Anclaje a la terminal | sí | **v1: flota** donde lo dejes (anclaje Quartz, pendiente) |

## Instalación

```bash
cd ~/Desktop/InProgress/dicta
python3 -m venv .venv
.venv/bin/pip install -e .
```

(La primera ejecución descarga el modelo Whisper. `large-v3` ≈ 3 GB y en CPU es
lento; para Mac recomiendo `model = "small"` o `"medium"` en el config.)

### Manos libres (wake-word "Claude") — necesita Python ≤ 3.12
El motor de wake-word (`vosk`) **aún no tiene wheels para Python 3.13**. El dictado
por **click NO lo necesita** y funciona en 3.13. Para usar manos libres, crea el
venv con Python 3.11/3.12 e instala el extra:
```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[handsfree]"
```
Si manos libres está activado pero `vosk` no está instalado, dicta lo detecta, lo
apaga solo y el dictado por click sigue funcionando.

## Permisos de macOS (IMPORTANTE)
La primera vez, macOS pedirá / habrá que conceder en **Ajustes → Privacidad y seguridad**:
- **Micrófono** → para la terminal/Python que ejecuta dicta.
- **Accesibilidad** → para que pueda enviar **Cmd+V** y el Enter (pynput). Sin esto,
  el texto queda en el portapapeles pero no se pega solo.

## Uso

```bash
.venv/bin/python -m dicta
```

- **Click** en el widget → empezar/terminar dictado (pega, no envía; revisas tú).
- **Manos libres**: di "Claude", habla, y al callarte se transcribe y envía solo.
- **Click derecho** → Manos libres / Salir.

## Config (`~/Library/Application Support/dicta/config.toml`)
Se crea sola la primera vez. En Mac, considera:
```toml
[whisper]
model = "small"        # CPU: small/medium van mucho más rápido que large-v3
[inyeccion]
paste_shortcut = "cmd+v"
```

## Hooks de Claude Code (auto-arranque)
Usa los `.sh` (ajusta la ruta del repo dentro de `session-start.sh`). En
`~/.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "bash \"$HOME/Desktop/InProgress/dicta/hooks/session-start.sh\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command",
      "command": "bash \"$HOME/Desktop/InProgress/dicta/hooks/session-end.sh\"" }] }]
  }
}
```

## Pendiente (v2)
- Anclaje del widget a la ventana de la terminal (Quartz/CGWindowList).
- Probar a fondo: captura de micrófono, transcripción en CPU, y el pegado con
  permisos de Accesibilidad (requiere prueba manual en el Mac).
