# dicta — Dictado por voz para Claude Code (spec de diseño)

**Fecha:** 2026-06-11
**Estado:** aprobado por Robert (diseño v2)
**Licencia:** MIT — repo público `irisdigitllab/dicta`

## Propósito

Hablarle a Claude Code en lugar de escribir. Al abrir `claude` en la terminal aparece un
widget flotante (icono con teléfono azul) en una esquina de la pantalla; un click activa
la escucha, otro click transcribe localmente con Whisper y escribe el texto en el prompt
de Claude Code. El usuario revisa y envía con Enter. Nada sale a la nube: STT 100% local.

## Entorno objetivo

- PC de escritorio Windows 11 x64 con **NVIDIA RTX 5060** (Blackwell → requiere CUDA 12.8+).
- Python 3.11+.
- El desarrollo puede hacerse en otra máquina, pero la validación real (CUDA, micrófono,
  widget, foco) se hace en el desktop.

## Experiencia de uso

1. Robert abre la terminal y ejecuta `claude`.
2. El hook `SessionStart` de Claude Code lanza `dicta` (si no está ya corriendo).
   Aparece el widget: icono en reposo (teléfono azul), always-on-top, arrastrable,
   posición persistida entre sesiones.
3. **Click** en el widget → sonido corto + estado "escuchando" (pulso rojo) → Robert habla.
4. **Click de nuevo** → estado "transcribiendo" (spinner) → al terminar, el texto aparece
   escrito en el prompt de la terminal que estaba activa.
5. Robert revisa y pulsa Enter él mismo. **dicta nunca envía el prompt** (no simula Enter).
6. Al cerrar la última sesión de Claude Code, el hook `SessionEnd` cierra el widget.

Salida manual: click derecho en el widget → menú con "Salir".

## Arquitectura

Un solo proceso Python. Cinco componentes con responsabilidad única:

| Componente | Responsabilidad | Tecnología |
|---|---|---|
| `widget` | Ventana frameless always-on-top; estados visuales reposo / escuchando / transcribiendo / error; drag para mover; click = toggle | PyQt6 |
| `focus_tracker` | Recordar cuál era la ventana en primer plano antes de que el click en el widget robara el foco (poll de `GetForegroundWindow` cada ~500 ms, ignorando al propio widget) | pywin32 |
| `recorder` | Capturar micrófono mientras el estado es "escuchando" (16 kHz, mono) | sounddevice (WASAPI) |
| `transcriber` | Whisper local: `faster-whisper`, modelo `large-v3`, `device=cuda`, `compute_type=float16`, `language=es`, `initial_prompt` con vocabulario técnico del config | faster-whisper (CTranslate2) |
| `injector` | Guardar clipboard actual → poner transcripción → devolver foco a la ventana recordada → simular paste (`Ctrl+V` por defecto, configurable) → restaurar clipboard | pywin32 |

Flujo: click → `focus_tracker` ya sabe la ventana destino → `recorder` graba →
click → `transcriber` procesa → `injector` pega → widget vuelve a reposo.

## Integración con Claude Code (hooks)

En `~/.claude/settings.json` del desktop:

- **`SessionStart`** → script lanzador: incrementa un contador de sesiones en un archivo
  de estado y arranca `dicta` si no hay instancia (singleton vía lockfile).
- **`SessionEnd`** → decrementa el contador; si llega a 0, cierra `dicta` (señal al proceso).

El contador evita que cerrar una de dos sesiones simultáneas de Claude Code mate el widget.
El repo incluye los snippets de hooks listos para copiar y un script de instalación opcional.

## Configuración (`config.toml`)

```toml
[whisper]
model = "large-v3"        # fallback automático documentado abajo
language = "es"
vocabulario = ["Netlify", "Turbopack", "GSAP", "deploy", "commit", "branch", "merge"]

[ui]
posicion = "auto"          # persistida tras arrastrar
sonidos = true

[inyeccion]
paste_shortcut = "ctrl+v"  # Windows Terminal acepta Ctrl+V

[hotkey]
enabled = false            # alternativa opcional al click
combo = "ctrl+alt+v"
```

## Manejo de errores

- **Sin CUDA / driver insuficiente:** fallback automático a CPU `int8` con aviso en el
  widget (tooltip) y en el log. Funciona, solo más lento.
- **Sin micrófono / permiso denegado:** estado "error" en el widget con tooltip explicando.
- **Transcripción vacía** (silencio, ruido): se descarta, sonido de error suave, no se pega nada.
- **Ventana destino cerrada** antes de pegar: no pegar a ciegas; dejar la transcripción en
  el clipboard y avisar con sonido (el usuario puede pegar manualmente).
- **Primera ejecución:** descarga del modelo (~3 GB para `large-v3`) con indicación de progreso en consola.

## Testing

- **Unit tests** (corren en cualquier máquina, sin GPU ni mic): parser de config,
  contador de sesiones del lanzador, lógica de estados del widget (máquina de estados
  separada de PyQt), armado del `initial_prompt`.
- **Checklist manual en el desktop** (documentada en el repo): ciclo completo click →
  hablar → pegar en Windows Terminal; spanglish técnico; dos sesiones de claude
  simultáneas; clipboard restaurado; fallback CPU desconectando CUDA.

## Fuera de alcance v1

- TTS / respuestas habladas
- Palabra clave de activación ("Claude…")
- Auto-Enter y comandos de voz
- UI de configuración (se edita el `config.toml` a mano)
- Empaquetado (instalador / PyInstaller); v1 se corre desde el repo con venv
- Soporte ARM64 / NPU

## Riesgos conocidos

1. **CTranslate2 + Blackwell (sm_120):** verificar al inicio de la implementación que la
   versión actual de `faster-whisper`/CTranslate2 soporta la 5060 con CUDA 12.8+. Si no,
   plan B: `whisper.cpp` con build CUDA, misma arquitectura, distinto backend.
2. **Robo de foco del widget:** PyQt permite ventanas que no aceptan foco
   (`WA_ShowWithoutActivating` + flags); si funciona, el `focus_tracker` se simplifica.
   Se decide en implementación; el spec asume el caso general (poll + restaurar foco).
3. **Icono:** diseño propio inspirado en Claude (estrella naranja + teléfono azul),
   sin usar el logo de Anthropic (marca registrada) en un repo público.
