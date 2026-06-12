# dicta

Dictado por voz **100% local** para [Claude Code](https://claude.com/claude-code) en Windows.

Abres Claude Code → aparece un botón flotante con el spark de Claude pegado a tu
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
- dicta **nunca pulsa Enter por ti**: revisas y envías tú.

## Integración con Claude Code (recomendado)

Con los hooks, dicta aparece al abrir `claude` y se cierra solo al salir.
Ver [`hooks/README.md`](hooks/README.md).

## Configuración

`%APPDATA%\dicta\config.toml` (se crea solo la primera vez). Ajusta el modelo,
el idioma y sobre todo el `vocabulario`: los términos técnicos que uses a diario
mejoran mucho la transcripción de spanglish.

## Licencia

MIT — [IRIS Digital Lab](https://github.com/irisdigitllab)
