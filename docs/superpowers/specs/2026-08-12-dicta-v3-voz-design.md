# dicta v3 — voz de salida (Claude te habla)

**Fecha:** 2026-08-12 · **Estado:** aprobado por Robert (brainstorm en sesión)
**Rama base:** `main` (v2 manos libres ya mergeada)

## Objetivo

Que dicta lea en voz alta lo que Claude Code le dice a Robert — avisos y el cierre de
cada respuesta — y que, cuando lo leído sea una pregunta, el micrófono se abra solo
para contestar. El reconocimiento actual (Whisper + wake word + VAD) no se toca.

## No-objetivos

- Leer las preguntas con opciones del formulario **AskUserQuestion**: el CLI de Claude
  Code no expone su texto a ningún hook (verificado 2026-08-12 contra la referencia de
  hooks). En la práctica casi todas las preguntas llegan como texto al final de una
  respuesta, que sí queda cubierto. Limitación documentada en README.
- Responder por voz a los diálogos de permisos (se contestan con teclas; un paste +
  Enter ahí sería peligroso). Solo se leen.
- Resumir con un LLM el cierre de la respuesta (descartado: mete latencia y rompe el
  100% local). Se lee el último párrafo tal cual.
- APIs de pago (Azure, OpenAI, ElevenLabs) y edge-tts: descartadas para v3 por
  filosofía (local, sin cuentas). Documentadas en el brainstorm por si algún día se
  quiere una voz premium.

## Decisiones tomadas (con el porqué)

| Decisión | Elección | Por qué |
|---|---|---|
| Qué se lee | Avisos (`Notification`) + último párrafo de cada respuesta (`Stop`) | Elegido por Robert sobre "solo avisos" y "todo" |
| El "cierre" | Último párrafo tal cual, tope ~400 chars cortando por frase | Heurística local, cero dependencias y cero latencia |
| Tras leer una pregunta | El mic se abre solo (ding + VAD + timeout) | Conversación fluida real; elegido por Robert |
| Motor TTS | **Kokoro-82M vía `kokoro-onnx`**, voz `ef_dora` | Mejor voz es del segmento ligero, Apache 2.0, sin cuentas; ONNX evita arrastrar PyTorch (~2,5 GB) |
| Plan B de motor | Piper (`es_ES`) | Más robótico pero trivial de encajar: misma interfaz interna en `speaker.py` |
| Puente Claude → dicta | Hooks `Notification`/`Stop` → cola de archivos en `%APPDATA%\dicta\speak\` | Mismo patrón que el contador de sesiones; sin sockets ni servidores |

## Diseño

### 1. Hooks (`hooks/notification.ps1`, `hooks/stop.ps1`)

- Mismo contrato que los hooks actuales: deducen la ruta de su propia ubicación, no
  bloquean, salen rápido y en silencio si algo falla.
- **`notification.ps1`**: lee el JSON de stdin; si `notification_type` ∈
  {`permission_prompt`, `idle_prompt`, `agent_needs_input`} escribe el `message` en la
  cola. El resto de tipos (auth, MCP, elicitation) se ignora.
- **`stop.ps1`**: usa `last_assistant_message` del payload; si el campo no viene
  (versiones viejas del CLI), fallback a parsear la última línea `assistant` del
  `transcript_path` (JSONL). Extrae el último párrafo, aplica el tope y escribe.
- Formato de la cola: un archivo por mensaje, `<ts>-<kind>.json` con
  `{ts, kind: "aviso"|"permiso"|"cierre", text}`. `kind="permiso"` distingue los
  avisos que NO abren mic.

### 2. Cola y watcher (en `app.py`)

- QTimer de 500 ms vigila `%APPDATA%\dicta\speak\`; lee por orden de nombre y borra.
- **Coalescing**: si hay varios pendientes, se queda el último `cierre` + los
  avisos/permisos no leídos; nunca una retahíla de cierres atrasados.
- Archivo corrupto o ilegible: se borra y se sigue.

### 3. Motor de voz (`speaker.py`, nuevo)

- `kokoro-onnx` (ONNX Runtime): modelo `kokoro-v1.0.onnx` + `voices-v1.0.bin`
  (~300 MB) descargados la primera vez a `%APPDATA%\dicta\models\kokoro\` con progreso
  en consola — mismo patrón `ensure_model` que Vosk.
- API interna: `Speaker.speak(text) -> None` (sintetiza en hilo propio, reproduce por
  `sounddevice.OutputStream`) + `Speaker.stop()` (corta la reproducción) + callback
  `on_level(rms)` para las barras del widget + señal de fin.
- Voz y velocidad desde config. Español vía G2P espeak-ng (lo trae `kokoro-onnx`).
- Si no carga o no descarga: voz OFF + aviso en consola; **el resto de dicta sigue
  intacto** (mismo contrato que el wake word).

### 4. Máquina de estados (`state.py`)

Nuevo estado `SPEAKING`. La máquina sigue pura. La sesión de habla lleva un flag
`abre_mic` (cierre-con-pregunta o aviso de input → True; permiso o cierre sin
pregunta → False).

| Evento | Desde → hacia |
|---|---|
| `speak_request` | `ARMED`/`IDLE` → `SPEAKING` · en `LISTENING`/`TRANSCRIBING` queda en cola (el dictado nunca se interrumpe) |
| `speak_done` | `SPEAKING` → `LISTENING` (`handsfree=True`) si `abre_mic`, si no → reposo |
| `click` | `SPEAKING` → corta la voz → `LISTENING` (quieres contestar ya) |
| `fail` | cualquiera → `ERROR` (como hoy) |

- Heurística de pregunta: `¿` o `?` dentro de las dos últimas frases del texto leído
  (tras aplicar el tope de caracteres).
- El detector de wake word solo se suscribe en `ARMED` (ya es así), de modo que el TTS
  diciendo "Claude" **no** se auto-dispara: sin eco por construcción.
- La escucha abierta tras una pregunta usa el VAD y el timeout de 10 s existentes; la
  respuesta dictada va a `last_terminal_hwnd` con Enter automático (`auto_enviar`),
  como cualquier sesión manos libres.

### 5. Widget (`widget.py`)

- Menú: check nuevo **"Voz"** (mute al vuelo, simétrico al de "Manos libres").
- Estado `SPEAKING`: cápsula marfil con barras tinta que siguen la envolvente del
  audio reproducido (reutiliza `set_level()`); visualmente distinto de `LISTENING`
  (cápsula terracota).

### 6. Config (`config.toml`)

```toml
[voz]
activado = true
voz = "ef_dora"          # voz de Kokoro
velocidad = 1.0
max_caracteres = 400     # tope del cierre leído
leer_avisos = true
leer_cierres = true
escuchar_tras_pregunta = true
```

Defaults si la sección no existe (compatibilidad con configs v1/v2). Dependencia
nueva en `pyproject.toml`: `kokoro-onnx`. Instalación de hooks: `INSTALL.md` gana los
dos hooks nuevos en `~/.claude/settings.json`.

## Manejo de errores

- Kokoro no carga/descarga → voz OFF + aviso; el flujo de dictado nunca se rompe.
- Salida de audio falla a mitad → se descarta el mensaje, log a consola, estado a
  reposo (sin `ERROR`: hablar es accesorio, dictar es lo esencial).
- Cola: archivos corruptos se borran; mensajes con texto vacío se ignoran.
- `stop.ps1` sin `last_assistant_message` ni transcript legible → no escribe nada.

## Testing

**Unitario (pytest, sin Qt ni hardware):**
- Extracción del último párrafo + tope por frase (texto corto, largo, con código,
  con listas).
- Heurística de pregunta (con `¿`, con `?` final, sin pregunta, pregunta a mitad).
- Coalescing de la cola (N cierres + M avisos pendientes → 1 cierre + M avisos).
- Transiciones `SPEAKING` (speak en reposo, en cola durante dictado, click corta,
  `abre_mic` en ambos valores).
- Parseo de `[voz]` con y sin sección.
- Filtro de `notification_type` del hook (lógica portada a Python testeable o
  probada vía fixture de payloads).

**Manual (`docs/manual-test-checklist.md`, ampliar):**
- Respuesta de Claude que termina en pregunta → dicta la lee → ding → contestas →
  aparece en la terminal con Enter.
- Respuesta sin pregunta → dicta lee el cierre y vuelve a reposo sin abrir mic.
- Aviso de permiso → lo lee, NO abre mic.
- Click durante la lectura corta la voz y abre escucha.
- El TTS diciendo "Claude" no dispara el wake word.
- Check "Voz" del menú apaga/enciende al vuelo.
- **Validar la voz `ef_dora` con los oídos de Robert**; si no convence, plan B Piper.

## Riesgos conocidos

1. **Calidad del español de Kokoro**: menos datos de entrenamiento que su inglés.
   Mitigado: validación auditiva en checklist; `speaker.py` aísla el motor y caer a
   Piper es un cambio local.
2. **Payload del hook `Stop` según versión del CLI** (`last_assistant_message`):
   mitigado con fallback al transcript JSONL.
3. **Varias sesiones de Claude Code a la vez**: los cierres de todas hablan por la
   misma voz. Aceptado para v3 (igual que hoy comparten el mismo widget); si molesta,
   filtrar por sesión en v3.1.
4. **Latencia primera síntesis** (carga del modelo ONNX): se carga en background al
   arrancar, como Whisper y Vosk.
