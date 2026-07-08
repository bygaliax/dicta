# dicta

Dictado por voz **100% local** para [Claude Code](https://claude.com/claude-code) en Windows.

Abres Claude Code → aparece un botón flotante con barras de ecualizador, anclado a
tu terminal, que se estira en cápsula al escuchar → hablas → tu voz aparece escrita
en el prompt. Whisper corre en tu GPU; nada sale a internet.

Dos modos: **click** (click para empezar, click para terminar, tú revisas y envías)
y **manos libres** (dices "Claude", hablas, y al callarte se transcribe y se envía
solo). Whisper para transcribir, Vosk para la palabra clave — ambos en local.

## Requisitos

- Windows 11 x64
- Python 3.11+
- GPU NVIDIA con driver reciente (CUDA 12.8+ para RTX serie 50). Sin GPU funciona
  en CPU (más lento; usa `model = "small"` en el config).
- Micrófono

## Instalación

```powershell
git clone https://github.com/irisdigitllab/dicta.git
cd dicta
python -m venv .venv
.venv\Scripts\pip install -e .
# DLLs de CUDA que faster-whisper necesita en Windows:
.venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

dicta registra automáticamente esas DLLs al arrancar (busca las carpetas
`Lib\site-packages\nvidia\*\bin` del venv), así que no hace falta tocar el PATH.

## Uso manual

```powershell
.venv\Scripts\python -m dicta
```

La primera ejecución descarga el modelo (~3 GB para `large-v3`). El widget se ancla
a la esquina inferior derecha de tu terminal y la sigue si la mueves; arrástralo
para ajustar dónde queda (el ajuste se recuerda). Si la terminal se minimiza, se
oculta con ella; sin terminal a la vista, flota donde estaba.

- **Click** — empezar/terminar dictado. El texto se pega en la ventana que estaba activa.
- **Click derecho → Salir** — cerrar.
- dicta **nunca pulsa Enter por ti** en el modo click: revisas y envías tú (el modo manos libres sí lo hace, ver abajo).

## Manos libres ("Claude")

Con `[manos_libres] activado = true` (default), dicta escucha en local la palabra
**"Claude"** (Vosk, modelo pequeño en español, sin nube ni cuentas). Di "Claude",
habla, y al callarte ~2 s dicta transcribe, pega el texto en la terminal y lo envía
con Enter automático (`auto_enviar = false` para desactivar el Enter). El dictado
por click sigue igual: pega sin enviar, tú revisas. Click derecho en el botón →
"Manos libres" para apagarlo/encenderlo al vuelo.

Para frenar falsos positivos, el detector solo confirma resultados **finales** de
Vosk (no parciales), exige una **confianza mínima** por palabra (`confianza`, 0.85
por defecto) y mete señuelos fonéticos en la gramática para que lo parecido a
"claude" no se fuerce a la wake word. Si aún se cuela ruido, sube `confianza` hacia
1.0; si te cuesta que te oiga, bájala. En llamadas largas, apágalo si molesta.

## Integración con Claude Code (recomendado)

Con los hooks, dicta aparece al abrir `claude` y se cierra solo al salir.
Ver [`hooks/README.md`](hooks/README.md).

## Cómo funciona

dicta abre **un solo** stream de micrófono (16 kHz mono) y lo reparte por un
**AudioBus** compartido a quien lo necesite, sin pelearse por el dispositivo:

- **Wake word** (Vosk, local): escucha la palabra clave solo en estado `ARMED`.
- **Recorder**: acumula audio mientras dictas (`LISTENING`).  `
- **SilenceDetector** (VAD): en manos libres, corta solo al detectar silencio sostenido.
- **Whisper** (faster-whisper, GPU): transcribe al terminar (`TRANSCRIBING`).
- **Injector**: pega el texto en la ventana activa (y pulsa Enter en manos libres).

La máquina de estados encadena el flujo y el widget refleja cada estado:

| Estado | Qué pasa | Widget |
|---|---|---|
| `IDLE` | Manos libres apagado; espera click | barras en calma |
| `ARMED` | Manos libres on; espera la palabra "Claude" | onda suave |
| `LISTENING` | Grabando tu voz | cápsula viva con nivel del micro |
| `TRANSCRIBING` | Whisper transcribe | puntos |

## Configuración

`%APPDATA%\dicta\config.toml` se crea solo la primera vez (copiado de
[`config.example.toml`](config.example.toml); nunca se sobrescribe). Si el TOML
está corrupto, dicta usa los valores por defecto y avisa por stderr.

```toml
[whisper]
model = "large-v3"            # large-v3 | medium | small (small si vas por CPU)
language = "es"
vocabulario = ["Netlify", "GSAP", "deploy", "commit", "Claude Code"]

[ui]
sonidos = true               # pitidos de inicio/fin/error

[inyeccion]
paste_shortcut = "ctrl+v"    # atajo de pegado de tu terminal

[hotkey]
enabled = false              # atajo global para iniciar/terminar dictado (= click)
combo = "ctrl+alt+v"

[manos_libres]
activado = true              # escuchar la wake word en local
palabra = "claude"           # se normaliza a minúsculas
confianza = 0.85             # 0–1: más alto = menos falsos positivos (y más exigente)
silencio_segundos = 2.0      # silencio que cierra el dictado manos libres
auto_enviar = true           # pulsar Enter tras pegar (solo manos libres)
```

El `vocabulario` es lo que más mejora la transcripción de spanglish: mete los
términos técnicos que uses a diario. La sección `[manos_libres]` controla el modo
wake word (Vosk, ~39 MB, se descarga la primera vez que se activa).

## Desarrollo

```powershell
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m pytest          # 65 tests
```

Para calibrar el wake word en vivo (ver qué reconoce Vosk y con qué confianza, y
ajustar el umbral) hay un arnés manual:

```powershell
.venv\Scripts\python tests\manual_wakeword_live.py
```

## Licencia

MIT — [IRIS Digital Lab](https://github.com/irisdigitllab)
