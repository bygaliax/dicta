# dicta

Dictado por voz **100% local** para [Claude Code](https://claude.com/claude-code) en Windows.

Abres Claude Code → aparece un botón flotante con barras de ecualizador que se estira en cápsula al escuchar pegado a tu
terminal → click → hablas → click → tu voz aparece escrita en el prompt. Whisper
corre en tu GPU; nada sale a internet.

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
"Manos libres" para apagarlo/encenderlo al vuelo. Riesgo conocido: hablar mucho
cerca del micro puede disparar falsos positivos; apágalo en llamadas si molesta.

## Integración con Claude Code (recomendado)

Con los hooks, dicta aparece al abrir `claude` y se cierra solo al salir.
Ver [`hooks/README.md`](hooks/README.md).

## Configuración

`%APPDATA%\dicta\config.toml` (se crea solo la primera vez). Ajusta el modelo,
el idioma y sobre todo el `vocabulario`: los términos técnicos que uses a diario
mejoran mucho la transcripción de spanglish. La sección `[manos_libres]` controla
el modo wake word (Vosk, ~39 MB, se descarga la primera vez que se activa).

## Licencia

MIT — [IRIS Digital Lab](https://github.com/irisdigitllab)
