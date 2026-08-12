# dicta

Dictado por voz **100% local** para [Claude Code](https://claude.com/claude-code) en Windows.

Abres Claude Code → aparece un botón flotante con barras de ecualizador, anclado a
tu terminal, que se estira en cápsula al escuchar → hablas → tu voz aparece escrita
en el prompt. Whisper corre en tu GPU; nada sale a internet.

Dos modos: **click** (click para empezar, click para terminar, tú revisas y envías)
y **manos libres** (dices "Claude", hablas, y al callarte se transcribe y se envía
solo). Whisper para transcribir, Vosk para la palabra clave — ambos en local.

**Voz de salida (v3):** dicta lee los avisos y el cierre de cada respuesta de
Claude con TTS 100% local (Kokoro), y si termina en pregunta abre el micrófono
para que contestes. Ver [Voz de salida](#voz-de-salida-claude-te-habla).

## Requisitos

- Windows 11 x64 · Python 3.11–3.13 (64 bits) · micrófono
- GPU NVIDIA con driver CUDA 12.x (12.8+ para RTX serie 50). **Opcional**: sin GPU
  funciona en CPU, más lento (usa `model = "small"` en el config).
- ¿Mac? El port a macOS vive en la rama [`mac`](https://github.com/bygaliax/dicta/tree/mac),
  todavía sin mergear. Ver [INSTALL.md](INSTALL.md#3-instalación-en-macos).

## Instalación

```powershell
git clone https://github.com/bygaliax/dicta.git
cd dicta
python -m venv .venv
.venv\Scripts\pip install -e .
# Solo con GPU NVIDIA — DLLs de CUDA que faster-whisper necesita en Windows:
.venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

dicta registra automáticamente esas DLLs al arrancar (busca las carpetas
`Lib\site-packages\nvidia\*\bin` del venv), así que no hace falta tocar el PATH.

**Guía completa paso a paso, verificación y solución de problemas:
[INSTALL.md](INSTALL.md).**

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

## Voz de salida (Claude te habla)

Con los hooks `Notification` y `Stop` de Claude Code (instalación en
[INSTALL.md §5](INSTALL.md#5-hooks-de-claude-code-arranque-automático)), dicta lee
en voz alta lo que Claude te dice: los avisos (permisos, "esperando input") y el
último párrafo de cada respuesta. Si lo leído termina en pregunta, se abre el
micrófono solo (ding + espera) para que contestes hablando; si no, dicta vuelve a
reposo sin abrir el mic. Un click durante la lectura corta la voz al momento y
abre el micrófono, por si prefieres contestar ya.

La síntesis es **Kokoro-82M** vía [`kokoro-onnx`](https://github.com/thewh1teagle/kokoro-onnx),
voz `ef_dora` (española), **100% local**: nada de lo leído sale a internet. El
modelo (~310 MB) se descarga solo, la primera vez, a
`%APPDATA%\dicta\models\kokoro\`. Si Kokoro no llega a cargar (sin red la primera
vez, sin espacio, etc.), dicta avisa por consola y sigue funcionando con la voz
apagada — no rompe el dictado. Click derecho en el widget → **Voz** para
apagarla/encenderla al vuelo.

El cierre que se lee es el **último párrafo** de la respuesta, cortado a
`max_caracteres` (400 por defecto) por frase para no dejarlo a medias. Los avisos
de permisos **se leen pero nunca abren el micrófono** — se contestan con teclado,
nunca por voz. Configuración completa en `[voz]`, ver [más abajo](#configuración).

> **Limitación conocida.** Las preguntas con formulario de opciones
> (`AskUserQuestion`) no se leen: el CLI de Claude Code no expone su texto a
> ningún hook. En la práctica, casi todas las preguntas de Claude llegan como
> texto normal al final de la respuesta, que sí se lee.

## Integración con Claude Code (recomendado)

Con los hooks, dicta aparece al abrir `claude` y se cierra solo al salir.
Ver [`hooks/README.md`](hooks/README.md). La voz de salida usa dos hooks más
(`Notification`/`Stop`), ver arriba.

## Cómo funciona

dicta abre **un solo** stream de micrófono (16 kHz mono) y lo reparte por un
**AudioBus** compartido a quien lo necesite, sin pelearse por el dispositivo:

- **Wake word** (Vosk, local): escucha la palabra clave solo en estado `ARMED`.
- **Recorder**: acumula audio mientras dictas (`LISTENING`).  `
- **SilenceDetector** (VAD): en manos libres, corta solo al detectar silencio sostenido.
- **Whisper** (faster-whisper, GPU): transcribe al terminar (`TRANSCRIBING`).
- **Injector**: pega el texto en la ventana activa (y pulsa Enter en manos libres).
- **Speaker** (Kokoro ONNX, local): sintetiza y reproduce avisos y cierres (`SPEAKING`).

La máquina de estados encadena el flujo y el widget refleja cada estado:

| Estado | Qué pasa | Widget |
|---|---|---|
| `IDLE` | Manos libres apagado; espera click | barras en calma |
| `ARMED` | Manos libres on; espera la palabra "Claude" | onda suave |
| `LISTENING` | Grabando tu voz | cápsula viva con nivel del micro |
| `TRANSCRIBING` | Whisper transcribe | puntos |
| `SPEAKING` | dicta lee un aviso o un cierre en voz alta | cápsula marfil con barras vivas; click corta y abre el mic |

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

[voz]
activado = true               # voz de salida on/off (también desde el menú del widget)
voz = "ef_dora"                # voz de Kokoro (español: ef_dora, em_alex, em_santa)
velocidad = 1.0
max_caracteres = 400           # tope del cierre leído en voz alta
leer_avisos = true             # permisos y "esperando input"
leer_cierres = true            # último párrafo de cada respuesta
escuchar_tras_pregunta = true  # abrir el mic solo si lo leído es una pregunta
```

El `vocabulario` es lo que más mejora la transcripción de spanglish: mete los
términos técnicos que uses a diario. La sección `[manos_libres]` controla el modo
wake word (Vosk, ~39 MB, se descarga la primera vez que se activa). La sección
`[voz]` controla la voz de salida (Kokoro, ~310 MB, se descarga la primera vez
que arranca dicta con `activado = true`); detalle en
[Voz de salida](#voz-de-salida-claude-te-habla).

## Desarrollo

```powershell
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m pytest          # 106 tests
```

Para calibrar el wake word en vivo (ver qué reconoce Vosk y con qué confianza, y
ajustar el umbral) hay un arnés manual:

```powershell
.venv\Scripts\python tests\manual_wakeword_live.py
```

## Licencia

MIT — [Galiax](https://github.com/bygaliax)
