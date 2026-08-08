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
git clone https://github.com/bygaliax/dicta.git
cd dicta
git checkout mac          # el port de macOS vive en esta rama, no en main
python3 -m venv .venv
.venv/bin/pip install -e .
```

(La primera ejecución descarga el modelo Whisper. `large-v3` ≈ 3 GB y en CPU es
lento; para Mac recomiendo `model = "small"` o `"medium"` en el config.)

### Manos libres (wake-word "Claude")
El dictado por **click NO lo necesita**; el wake-word va en un extra aparte:
```bash
.venv/bin/pip install -e ".[handsfree]"
```

> **Corregido el 2026-08-08.** Aquí se decía que hacía falta Python 3.11/3.12
> "porque vosk no tiene wheels para 3.13". El diagnóstico era otro: la última
> versión de vosk (0.3.45) no publica wheel de macOS **para ninguna versión de
> Python**; la última que sí la trae es la 0.3.44. Como el proyecto pide
> `vosk>=0.3.42`, pip retrocede solo a la 0.3.44, cuya wheel es `universal2` y
> vale en Intel y Apple Silicon con Python 3.11, 3.12 **y 3.13**. Verificado
> resolviendo dependencias contra PyPI para las tres versiones y las tres
> arquitecturas; no se ha podido ejecutar en un Mac real.
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
Usa los `.sh`. **No hay que editarlos**: deducen la ruta del repo a partir de su
propia ubicación. Dales permiso de ejecución la primera vez y apúntalos desde
`~/.claude/settings.json` con la ruta real de tu clon:
```bash
chmod +x hooks/session-start.sh hooks/session-end.sh
```
```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "bash \"$HOME/ruta/a/dicta/hooks/session-start.sh\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command",
      "command": "bash \"$HOME/ruta/a/dicta/hooks/session-end.sh\"" }] }]
  }
}
```

## Tests
`pytest` deja **10 fallos esperados** en esta rama (`test_injector.py` 3,
`test_docking.py` 7): el port movió los imports de win32 dentro de las funciones
para que los módulos carguen en macOS, pero la suite sigue parcheándolos a nivel
de módulo. Es una laguna de los tests, no de la instalación:
```bash
.venv/bin/python -m pytest --ignore=tests/test_injector.py --ignore=tests/test_docking.py
```

## Pendiente (v2)
- Anclaje del widget a la ventana de la terminal (Quartz/CGWindowList).
- Probar a fondo: captura de micrófono, transcripción en CPU, y el pegado con
  permisos de Accesibilidad (requiere prueba manual en el Mac).
