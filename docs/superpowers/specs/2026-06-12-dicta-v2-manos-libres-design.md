# dicta v2 — manos libres, cápsula viva y fix de z-order

**Fecha:** 2026-06-12 · **Estado:** aprobado por Robert (brainstorm con companion visual)
**Rama base:** `feature/widget-dock-anim` (incluye docking; el visual del spark se reemplaza aquí)

## Objetivos

1. **Bug z-order:** el botón no debe flotar sobre otras apps cuando la terminal no está delante.
2. **Wake word "Claude":** modo manos libres — decir "Claude", hablar, y que dicta transcriba solo.
3. **Envío directo:** en manos libres, pegar + Enter automático en la terminal.
4. **Rediseño del botón:** identidad nueva "C1 · Ecualizador en calma" (elegida sobre mockups; el spark de Anthropic se descarta).

## No-objetivos

- Transcripción en streaming (se mantiene grabar → transcribir al final).
- Wake word en otros idiomas o frases multi-palabra (solo una palabra, default "claude").
- Manos libres hacia apps que no sean terminal (el Enter automático solo va a terminales).
- Cambiar el motor de transcripción (sigue faster-whisper `large-v3`).

## Decisiones tomadas (con el porqué)

| Decisión | Elección | Por qué |
|---|---|---|
| Comportamiento del botón sin foco | Vive justo encima de la terminal en el z-order | "Anclado de verdad": tapado cuando la tapan, emerge con ella |
| Fin del dictado manos libres | Silencio (default 2.0 s, configurable) | Manos libres real; sin palabras de cierre que recordar |
| Envío directo | Solo en manos libres (configurable) | Con el botón, Robert revisa antes de enviar; errores de Whisper no disparan prompts |
| Motor wake word | Vosk, modelo small español, modo gramática | 100% local y sin cuentas (filosofía de dicta); Porcupine descartado por licencia, openWakeWord por entrenar "Claude" sin garantías |
| Identidad visual | C1 · Ecualizador en calma | Elegida por Robert entre 4 direcciones y 2 variantes |

## Diseño

### 1. Fix z-order (`docking.py`, `widget.py`)

- Se elimina `WindowStaysOnTopHint` del widget.
- En cada `Docker.tick()` con terminal viva y visible: además de posicionar, colocar el widget **inmediatamente encima de la terminal en el z-order** (`win32gui.SetWindowPos` con `hWndInsertAfter` = la ventana que está encima de la terminal, `SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE`; si esa ventana ya es el widget, no hacer nada).
- Sin terminal viva: el widget queda como ventana normal (sin topmost).
- Minimizada: se oculta (igual que hoy).

### 2. Widget "Ecualizador en calma" (`widget.py`)

Círculo de 52 px; la identidad son **5 barras verticales de ecualizador** (4 px de ancho, bordes redondeados, alturas en reposo 7/12/17/12/7 px). Al trabajar se estira en **cápsula de ~116 px** creciendo **hacia la izquierda** (el borde derecho queda fijo al ancla del dock). Expansión/colapso animados ~200 ms ease-out. El canvas de la ventana crece a `140×72` para alojar la cápsula; `dock_position` usa el tamaño actual.

| Estado | Visual |
|---|---|
| `LOADING` | Círculo marfil, barras grises quietas respirando (opacity 0.35↔0.95, 2.4 s) |
| `IDLE` (manos libres OFF) | Círculo marfil, barras terracota quietas |
| `ARMED` (esperando "Claude") | Círculo marfil, onda lenta recorre las barras cada ~3.2 s (scaleY 0.4→0.95) |
| `LISTENING` | Cápsula terracota, barras marfil cuya altura sigue el **nivel real del micrófono** (RMS, ~30 fps, suavizado) |
| `TRANSCRIBING` | Cápsula tinta, 3 puntos marfil pulsando (delay escalonado 0.2 s) |
| `ERROR` | Círculo rojo `#A12A22`, "!" construido con barra + punto en marfil |

Paleta: marfil `#F5F4EF`, terracota `#D97757`, tinta `#262625`, gris `#A8A49C`. Sombra y borde sutil como hoy. Solo se anima transform/opacity (sin layout) salvo la expansión de la cápsula, que anima el ancho de la ventana una vez por sesión de dictado.

Interacción: igual que hoy (click dicta/para, drag mueve, click derecho menú). El menú gana **"Manos libres"** (checkable) para armar/desarmar el wake word al vuelo. API nueva del widget: `set_level(float)` para las barras en `LISTENING`.

### 3. Bus de audio (`audio.py`, nuevo)

Un solo `sounddevice.InputStream` (16 kHz mono float32) compartido por wake word, grabadora y VAD — evita pelea por el dispositivo y alimenta el nivel de voz del widget.

- API: `subscribe(callback)` / `unsubscribe(callback)`; el stream se abre con el primer suscriptor y se cierra con el último.
- Con manos libres ON: el detector de wake word mantiene el stream abierto mientras está `ARMED`/`LISTENING`.
- Con manos libres OFF: solo la grabadora se suscribe al dictar (comportamiento actual).
- `Recorder` pasa de abrir su propio stream a suscribirse al bus.
- El bus publica RMS por chunk; `app.py` lo lleva al widget vía señal Qt (throttled).
- Si el stream muere (micrófono desconectado): error a consola, estado `ERROR`, reintento al hacer click.

### 4. Wake word (`wakeword.py`, nuevo)

- **Vosk** con `vosk-model-small-es-0.42` (~39 MB) en **modo gramática**: `KaldiRecognizer(model, 16000, '["claude", "[unk]"]')` — todo lo que no sea la palabra cae en `[unk]`.
- La palabra es configurable (`palabra = "claude"`); una sola palabra, en minúsculas.
- Descarga automática del modelo la primera vez (zip oficial de alphacephei.com → `%APPDATA%\dicta\models\`), con progreso en consola. Sin red y sin modelo: aviso en consola y manos libres queda desactivado; el flujo manual no se ve afectado.
- Corre como suscriptor del bus de audio en hilo propio; emite `wake_detected` (señal Qt vía Bridge) cuando la palabra aparece en un resultado parcial o final, con debounce de 1 s.
- Mientras el estado no es `ARMED` (dictando, transcribiendo, error), el detector descarta audio — decir "Claude" durante un dictado no hace nada.
- Al detectar: sonido "start" (el ding existente) + transición a `LISTENING`.

### 5. Fin por silencio (VAD)

- Silero VAD **reutilizando el que ya trae faster-whisper** (`faster_whisper.vad`) — sin dependencia nueva.
- Activo **solo en sesiones iniciadas por wake word**: evalúa el audio en ventanas de ~0.5 s; tras `silencio_segundos` (default 2.0) continuos sin voz **después de haber detectado voz**, dispara `silence_detected` → `TRANSCRIBING`.
- Si nunca llega voz, timeout de seguridad (10 s) → cancela sin transcribir, sonido de error suave, vuelve a `ARMED`.
- En sesiones por click no hay VAD: el usuario corta con click (como hoy). Un click durante una sesión manos libres también corta inmediatamente.

### 6. Máquina de estados (`state.py`)

Nuevo estado `ARMED`. La máquina sigue pura (sin Qt). La sesión lleva un flag `handsfree` (origen wake word vs click) que decide VAD, destino y auto-envío.

Transiciones:

| Evento | Desde → hacia |
|---|---|
| `model_ready` | `LOADING` → `ARMED` (manos libres ON) o `IDLE` (OFF) |
| `wake_detected` | `ARMED` → `LISTENING` (`handsfree=True`) |
| `click` | `IDLE`/`ARMED` → `LISTENING` (`handsfree=False`) · `LISTENING` → `TRANSCRIBING` · `ERROR` → `IDLE`/`ARMED` |
| `silence_detected` | `LISTENING` (solo `handsfree`) → `TRANSCRIBING` |
| `transcription_done` | `TRANSCRIBING` → `ARMED` o `IDLE` según toggle |
| `toggle_handsfree` | `IDLE` ↔ `ARMED` |
| `fail` | cualquiera → `ERROR` |

### 7. Inyección y envío (`injector.py`, `app.py`)

- `inject()` gana parámetro `send_enter: bool`: tras el paste (y antes de restaurar el clipboard), envía `VK_RETURN` con `keybd_event` y una pausa corta (~80 ms).
- **Sesión manos libres:** destino = `tracker.last_terminal_hwnd` (nunca otra app); `send_enter = cfg.auto_enviar`. Sin terminal viva: sonido de error, texto queda en el clipboard, vuelve a `ARMED`.
- **Sesión por click:** destino = `tracker.last_hwnd`, sin Enter (comportamiento actual).

### 8. Config (`config.toml`)

```toml
[manos_libres]
activado = true          # arrancar armado (el menú permite cambiarlo en caliente)
palabra = "claude"       # wake word, una palabra en minúsculas
silencio_segundos = 2.0  # corte por silencio del dictado manos libres
auto_enviar = true       # Enter automático tras pegar (solo manos libres)
```

Defaults aplicados si la sección no existe (compatibilidad con configs v1). Dependencia nueva en `pyproject.toml`: `vosk`.

## Manejo de errores

- Vosk no carga / modelo no descargable → manos libres OFF + aviso; **el flujo manual nunca se rompe**.
- Stream de audio muere → `ERROR`; click reintenta (reabre el bus).
- `SetForegroundWindow` puede fallar por las restricciones de foco de Windows (riesgo ya existente en v1): si falla, el texto queda en clipboard y suena el error.
- Falsos positivos del wake word (llamadas, música con voz): mitigado por modo gramática + debounce + toggle del menú. Riesgo aceptado y documentado en README.

## Testing

**Unitario (pytest, sin Qt ni hardware):**
- Transiciones nuevas de la máquina de estados (wake, silencio, toggle, flag `handsfree`).
- Detector de silencio con audio sintético (silencio, voz, voz→silencio, nunca-voz→timeout).
- `dock_position` con ancho expandido (la cápsula no se desplaza del ancla).
- `inject` con `send_enter` (win32 mockeado).
- Parseo de config con y sin sección `[manos_libres]`.
- Lógica de gramática/debounce del wake word con un recognizer fake.

**Manual (`docs/manual-test-checklist.md`, ampliar):**
- Decir "Claude" → ding → dictar → silencio → texto enviado a Claude Code con Enter.
- Click durante sesión manos libres corta y transcribe.
- Tapar la terminal con otra app: el botón desaparece detrás; volver a la terminal: emerge.
- Toggle "Manos libres" del menú en ambos sentidos.
- Falso positivo: decir "Claude" en una frase normal de conversación cercana.

## Riesgos conocidos

1. **CPU del Vosk siempre activo** mientras está armado (~fracción de un core). Aceptado; el toggle permite apagarlo.
2. **Cápsula cerca del borde de pantalla:** la expansión hacia la izquierda se recorta si el ancla está pegada al borde izquierdo (caso raro: terminal de <140 px). Se clampa a pantalla.
3. **Pronunciación de "Claude"** (klod/klaud) con el modelo es: validar en checklist manual; si falla, la palabra es configurable (p. ej. "oye claude" no — una sola palabra, p. ej. "clode" fonético).
