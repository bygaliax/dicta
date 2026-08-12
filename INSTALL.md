# Instalación de dicta

Guía completa para instalar dicta en un ordenador nuevo, desde cero. Está pensada
para alguien que no ha visto el proyecto antes: cada paso dice qué hace, qué debe
salir por pantalla y qué hacer si sale otra cosa.

dicta es dictado por voz **100 % local**: Whisper transcribe en tu máquina y nada
sale a internet. Desde la v3 también te habla — lee avisos y el cierre de cada
respuesta con TTS local (Kokoro), ver [§5](#5-hooks-de-claude-code-arranque-automático)
— sin salir tampoco a la red. Solo necesitas conexión **durante la instalación** y
la primera ejecución (para bajar las dependencias y los modelos). A partir de ahí
funciona sin red.

> ### ⚠ Antes de nada: elige la rama correcta
>
> | Tu sistema | Rama | Motivo |
> |---|---|---|
> | **Windows** | `main` | Es la versión principal, probada en uso diario |
> | **macOS** | `mac` | El port a macOS **todavía no está mergeado en `main`**. Si clonas `main` en un Mac, dicta no arrancará |
>
> No es un olvido: el port de macOS está sin validar en un Mac físico (ver
> [§3.6](#36-limitaciones-conocidas-del-port-de-macos)), y por eso se mantiene aparte.

**Índice**

1. [Requisitos](#1-requisitos)
2. [Instalación en Windows](#2-instalación-en-windows)
3. [Instalación en macOS](#3-instalación-en-macos)
4. [Configuración](#4-configuración)
5. [Hooks de Claude Code (arranque automático)](#5-hooks-de-claude-code-arranque-automático)
6. [Verificación](#6-verificación)
7. [Problemas frecuentes](#7-problemas-frecuentes)
8. [Desinstalar](#8-desinstalar)

---

## 1. Requisitos

### Windows

| | Requisito |
|---|---|
| **Sistema** | Windows 11 x64 (validado en uso diario). Windows 10 x64 21H2+ debería funcionar, pero no está probado |
| **Python** | 3.11, 3.12 o 3.13, **de 64 bits**. Probado a diario en 3.12 |
| **GPU** | *Opcional.* NVIDIA con driver que soporte CUDA 12.x. Para las RTX serie 50 (Blackwell) hace falta un driver con CUDA 12.8 o superior. **Sin GPU también funciona**, en CPU (ver [§2.4](#24-sin-gpu-nvidia)) |
| **Micrófono** | Cualquiera que Windows reconozca como dispositivo de entrada |
| **Altavoces / auriculares** | Solo si usas la voz de salida (v3, [§5](#5-hooks-de-claude-code-arranque-automático)): cualquier dispositivo de salida que Windows reconozca |
| **Git** | Para clonar el repositorio |

Python 3.11 es el mínimo real, no una preferencia: dicta lee su configuración con
`tomllib`, que llegó en 3.11.

### macOS

| | Requisito |
|---|---|
| **Sistema** | macOS 11 Big Sur o superior, Intel o Apple Silicon |
| **Python** | 3.11, 3.12 o 3.13 |
| **GPU** | No se usa. faster-whisper **no** aprovecha Metal: en Mac la transcripción va **siempre por CPU** |
| **Micrófono** | Interno o externo |
| **Permisos** | Micrófono y Accesibilidad — **obligatorios**, ver [§3.4](#34-permisos-del-sistema-obligatorio) |

### Espacio en disco y red

| Concepto | Tamaño |
|---|---|
| Entorno virtual **con** soporte GPU (incluye las librerías CUDA) | ~2,5 GB |
| Entorno virtual **sin** GPU / en macOS | ~1,3 GB |
| Modelo Whisper `large-v3` (se descarga en la 1.ª ejecución) | ~3 GB |
| Modelo Whisper `small` (alternativa para CPU) | ~0,5 GB |
| Modelo Vosk del wake word (solo si usas manos libres) | ~39 MB |
| Modelo Kokoro de la voz de salida (solo si usas los hooks `Notification`/`Stop`, ver [§5](#5-hooks-de-claude-code-arranque-automático)) | ~310 MB |

En total: **~6 GB** en una instalación completa con GPU y `large-v3`; **~2 GB** en
una instalación de CPU con `small`. Si además usas la voz de salida, suma
**~310 MB** del modelo Kokoro.

Las descargas ocurren una sola vez. Después, dicta funciona sin conexión.

---

## 2. Instalación en Windows

### 2.1 Comprobar Python

Abre **PowerShell** y comprueba la versión:

```powershell
python --version
```

Debe responder `Python 3.11.x`, `3.12.x` o `3.13.x`. Si no tienes Python o la
versión es anterior, instálalo desde [python.org](https://www.python.org/downloads/windows/)
marcando **"Add python.exe to PATH"** durante la instalación.

> Si Windows te abre la Microsoft Store al escribir `python`, es el alias de
> ejecución de la Store interceptando el comando. Desactívalo en
> *Configuración → Aplicaciones → Configuración avanzada de aplicaciones →
> Alias de ejecución de aplicaciones* → apaga las entradas `python.exe` y
> `python3.exe`. Luego abre una PowerShell nueva.

### 2.2 Clonar e instalar

```powershell
git clone https://github.com/bygaliax/dicta.git
cd dicta
python -m venv .venv
.venv\Scripts\pip install -e .
```

Esto instala PyQt6 (la interfaz), faster-whisper (transcripción), sounddevice
(micrófono), pywin32 (ventanas y portapapeles), keyboard (atajo global), vosk
(palabra clave) y kokoro-onnx (voz de salida). Tarda unos minutos.

El entorno virtual queda dentro de `.venv\` y **no** se sube al repositorio. Todos
los comandos de esta guía lo invocan por su ruta (`.venv\Scripts\...`), así que no
hace falta "activar" nada.

### 2.3 Aceleración por GPU (NVIDIA)

Si tienes una GPU NVIDIA, instala también las librerías CUDA que necesita el motor
de transcripción:

```powershell
.venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

No hace falta instalar el CUDA Toolkit completo ni tocar el `PATH`: estas wheels
traen las DLL dentro del entorno virtual, y dicta las registra sola al arrancar
(busca las carpetas `Lib\site-packages\nvidia\*\bin` y las añade a la ruta de
búsqueda de DLL del proceso). Sí necesitas un **driver de NVIDIA** reciente, que
es lo único que no viene por pip.

`nvidia-cuda-nvrtc-cu12` se instala automáticamente como dependencia; no lo pidas
a mano.

### 2.4 Sin GPU NVIDIA

dicta funciona igual, solo que más lento. **No instales** las wheels de la sección
anterior y cambia el modelo a uno pequeño en la configuración
([§4](#4-configuración)):

```toml
[whisper]
model = "small"
```

No hay que desactivar nada más: dicta intenta CUDA, falla, avisa por consola y
sigue en CPU automáticamente.

```
CUDA no disponible (...); usando CPU int8.
```

Ese mensaje es informativo, no un error.

### 2.5 Primera ejecución

```powershell
.venv\Scripts\python -m dicta
```

La primera vez descarga el modelo de Whisper (~3 GB con `large-v3`), así que tarda.
La consola debe mostrar, en este orden:

```
Cargando modelo large-v3… (la primera vez descarga ~3 GB)
Modelo listo en cuda.
```

`Modelo listo en cpu.` significa que va por CPU — correcto si no tienes GPU, y
señal de que algo falta si sí la tienes (ver [§7](#7-problemas-frecuentes)).

El widget aparece en la esquina inferior derecha, anclado a tu terminal. Arrástralo
para colocarlo donde quieras: recuerda la posición entre ejecuciones.

- **Click** en el widget → empieza a dictar. **Otro click** → transcribe y pega el
  texto en la ventana que estaba activa. En este modo dicta **nunca pulsa Enter**:
  revisas tú y envías.
- **Click derecho → Salir** → cerrar.
- **Manos libres** (activado por defecto): di *"Claude"*, habla, y al callarte ~2 s
  dicta transcribe, pega en la terminal y **sí pulsa Enter**. Es el único modo que
  envía solo. Se apaga con click derecho → *Manos libres*, o con
  `auto_enviar = false` si solo quieres quitar el Enter.

La primera vez que se activa manos libres, la consola muestra la descarga del
modelo de la palabra clave:

```
Descargando modelo de wake word (vosk-model-small-es-0.42, ~39 MB)…
Modelo de wake word listo.
```

La voz de salida (`[voz] activado = true` por defecto, ver [§4](#4-configuración))
carga en un hilo aparte al arrancar, así que no bloquea el dictado. La primera vez
descarga el modelo Kokoro (~310 MB) a `%APPDATA%\dicta\models\kokoro\`:

```
Descargando kokoro-v1.0.onnx…
Descargando voices-v1.0.bin…
Voz lista.
```

Si algo falla (sin red, sin espacio, modelo corrupto), la consola muestra `Voz no
disponible: ...` y dicta sigue funcionando normal con la voz apagada — no rompe el
dictado.

### 2.6 Dónde queda todo

| Qué | Dónde |
|---|---|
| Configuración, estado del widget, PID, contador de sesiones | `%APPDATA%\dicta\` |
| Modelo del wake word (Vosk) | `%APPDATA%\dicta\models\` |
| Modelo de la voz de salida (Kokoro ONNX) | `%APPDATA%\dicta\models\kokoro\` |
| Modelos de Whisper (caché de Hugging Face) | `%USERPROFILE%\.cache\huggingface\hub\` |
| Dependencias de Python | `.venv\` dentro del clon |

Nada de esto va al repositorio.

---

## 3. Instalación en macOS

### 3.1 Clonar y cambiar a la rama `mac`

**Este paso no es opcional.** El código de macOS vive en la rama `mac`:

```bash
git clone https://github.com/bygaliax/dicta.git
cd dicta
git checkout mac
```

Comprueba que estás donde debes — el archivo `MAC.md` solo existe en esa rama:

```bash
git branch --show-current   # -> mac
ls MAC.md                   # -> MAC.md
```

### 3.2 Entorno e instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

En la rama `mac`, el `pyproject.toml` selecciona las dependencias por plataforma:
en vez de pywin32 y keyboard instala `pyobjc-framework-Cocoa` (para saber qué app
está en primer plano) y `pynput` (para enviar Cmd+V).

### 3.3 Manos libres (opcional)

El wake word usa `vosk`, que en la rama `mac` es un extra aparte. El dictado por
click **no lo necesita**:

```bash
.venv/bin/pip install -e ".[handsfree]"
```

> **Nota — corrección a `MAC.md`.** `MAC.md` dice que manos libres exige Python
> 3.11 o 3.12 "porque vosk no tiene wheels para Python 3.13". Eso ya no aplica, y
> además el diagnóstico era otro: la versión más reciente de vosk (0.3.45) no
> publica wheel de macOS **para ninguna versión de Python**; la última que sí la
> publica es la 0.3.44. Como el proyecto pide `vosk>=0.3.42`, pip retrocede solo a
> la 0.3.44, cuya wheel es `universal2` y sirve en Intel y Apple Silicon con
> Python 3.11, 3.12 **y 3.13**.
>
> Verificado el 2026-08-08 resolviendo dependencias contra PyPI para las tres
> versiones de Python y las tres arquitecturas. Comprobado que la wheel **existe y
> se resuelve**; no se ha podido ejecutar en un Mac real.

Si manos libres está activado en la configuración pero `vosk` no está instalado,
dicta lo detecta al arrancar, apaga el modo solo y sigue funcionando por click.

### 3.4 Permisos del sistema (OBLIGATORIO)

macOS bloquea por defecto lo que dicta necesita. En **Ajustes del Sistema →
Privacidad y seguridad**, concede a **la aplicación de terminal desde la que
lanzas dicta** (Terminal, iTerm2, etc.):

| Permiso | Para qué | Si falta |
|---|---|---|
| **Micrófono** | Capturar tu voz | dicta no oye nada; error de micrófono al dictar |
| **Accesibilidad** | Enviar Cmd+V y el Enter | La transcripción **se queda en el portapapeles** y no se pega sola |

Algunos permisos solo aparecen en la lista después del primer intento de uso: lanza
dicta, dicta una frase, y vuelve a Ajustes si no estaban.

### 3.5 Ajustes recomendados en Mac

En `~/Library/Application Support/dicta/config.toml`:

```toml
[whisper]
model = "small"           # en CPU, large-v3 es muy lento

[inyeccion]
paste_shortcut = "cmd+v"  # en Mac se pega con Cmd, no con Ctrl
```

### 3.6 Limitaciones conocidas del port de macOS

Documentadas por honestidad, no son fallos que vayas a poder arreglar:

- **El widget no se ancla a la terminal.** En Windows sigue a la ventana; en Mac
  flota donde lo dejes. El anclaje (vía Quartz) está pendiente.
- **Transcripción solo por CPU.** No hay aceleración por Metal.
- **El port no se ha validado en un Mac físico.** Faltan por probar a fondo la
  captura de micrófono, la transcripción en CPU y el pegado con permisos de
  Accesibilidad. Si algo no funciona, es terreno conocido: abre un issue.

---

## 4. Configuración

El archivo se crea **solo, la primera vez que arrancas**, copiado de
[`config.example.toml`](config.example.toml). Nunca se sobrescribe, así que tus
cambios sobreviven a los `git pull`.

| Sistema | Ruta |
|---|---|
| Windows | `%APPDATA%\dicta\config.toml` |
| macOS | `~/Library/Application Support/dicta/config.toml` |

Si el TOML tiene un error de sintaxis, dicta **no se cae**: usa todos los valores
por defecto y avisa por la salida de error (`config.toml inválido (...); usando
defaults.`). Un TOML válido pero con claves sueltas también vale — cada clave que
falte toma su valor por defecto.

### Referencia completa

**`[whisper]`**

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| `model` | texto | `"large-v3"` | Modelo de Whisper. `large-v3` (mejor calidad, ~3 GB, pide GPU), `medium`, `small` (recomendado en CPU) |
| `language` | texto | `"es"` | Idioma del dictado, en código ISO. `"en"` para inglés |
| `vocabulario` | lista | `[]` | Términos que Whisper debe reconocer bien. **Es lo que más mejora el spanglish técnico**: mete las palabras que uses a diario |

**`[ui]`**

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| `sonidos` | booleano | `true` | Pitidos al empezar, terminar y al fallar |

**`[inyeccion]`**

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| `paste_shortcut` | texto | `"ctrl+v"` | Atajo de pegado de tu terminal. `"cmd+v"` en Mac; `"ctrl+shift+v"` si tu terminal usa ese |

**`[hotkey]`**

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| `enabled` | booleano | `false` | Atajo global de teclado para empezar/terminar dictado, equivalente a hacer click en el widget |
| `combo` | texto | `"ctrl+alt+v"` | La combinación de teclas |

**`[manos_libres]`**

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| `activado` | booleano | `true` | Escuchar la palabra clave en local |
| `palabra` | texto | `"claude"` | La palabra que arma el dictado. Se pasa a minúsculas |
| `confianza` | número 0–1 | `0.85` | Umbral del detector. **Más alto = menos falsos positivos** pero cuesta más que te oiga |
| `silencio_segundos` | número | `2.0` | Silencio que cierra el dictado y dispara la transcripción |
| `auto_enviar` | booleano | `true` | Pulsar Enter tras pegar. **Solo afecta a manos libres**; el dictado por click nunca envía |

**`[voz]`** — voz de salida (v3, ver [§5](#5-hooks-de-claude-code-arranque-automático))

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| `activado` | booleano | `true` | Encender/apagar la voz de salida. También se cambia al vuelo desde el menú del widget (click derecho → Voz) |
| `voz` | texto | `"ef_dora"` | Voz de Kokoro. En español: `ef_dora`, `em_alex`, `em_santa` |
| `velocidad` | número | `1.0` | Multiplicador de velocidad de la síntesis |
| `max_caracteres` | número | `400` | Tope del cierre leído en voz alta (corta por frase, no a media palabra) |
| `leer_avisos` | booleano | `true` | Leer los avisos del hook `Notification` (permisos, "esperando input") |
| `leer_cierres` | booleano | `true` | Leer el último párrafo de cada respuesta (hook `Stop`) |
| `escuchar_tras_pregunta` | booleano | `true` | Abrir el micrófono solo (ding + espera) cuando lo leído termina en pregunta |

---

## 5. Hooks de Claude Code (arranque automático)

Opcional pero recomendado: con los hooks, dicta aparece al abrir `claude` y se
cierra sola al salir de la última sesión.

**Cómo funciona.** Cada sesión de Claude Code incrementa un contador en
`sessions.count` al abrir y lo decrementa al cerrar. dicta lo mira cada 2 segundos
y se cierra cuando llega a 0. Si lanzas dicta a mano el contador no existe, y
entonces dicta **nunca** se auto-cierra — que es lo que quieres al ejecutarla
suelta.

Los scripts deducen solos dónde está el repositorio a partir de su propia
ubicación, así que **no hay que editarlos**. Solo tienes que apuntar a ellos con la
ruta real de tu clon.

**Windows** — en `~/.claude/settings.json` (o sea, `%USERPROFILE%\.claude\settings.json`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\ruta\\a\\dicta\\hooks\\session-start.ps1\""
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\ruta\\a\\dicta\\hooks\\session-end.ps1\""
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\ruta\\a\\dicta\\hooks\\notification.ps1\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\ruta\\a\\dicta\\hooks\\stop.ps1\""
          }
        ]
      }
    ]
  }
}
```

Sustituye `C:\\ruta\\a\\dicta` por la ruta real de tu clon, en los cuatro bloques.
Las barras van **dobladas**, porque en JSON la barra invertida es un carácter de
escape.

`SessionStart`/`SessionEnd` abren y cierran dicta con la sesión (arriba).
`Notification`/`Stop` son la voz de salida (v3): `notification.ps1` encola los
avisos (permisos, "esperando input") y `stop.ps1` encola el cierre de cada
respuesta para que dicta lo lea con TTS local. Son independientes entre sí —
puedes registrar solo los dos primeros, solo los dos últimos, o los cuatro a la
vez. Configuración de la voz en `[voz]` ([§4](#4-configuración)).

**macOS** — mismo archivo, con los scripts `.sh` de la rama `mac`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOME/ruta/a/dicta/hooks/session-start.sh\""
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOME/ruta/a/dicta/hooks/session-end.sh\""
          }
        ]
      }
    ]
  }
}
```

Dale permiso de ejecución la primera vez:

```bash
chmod +x hooks/session-start.sh hooks/session-end.sh
```

> La voz de salida (`Notification`/`Stop`) todavía no tiene script `.sh`
> equivalente: por ahora es exclusiva de la rama `main` (Windows).

**Para quitarlos**, borra los bloques `SessionStart`, `SessionEnd`, `Notification`
y `Stop` (los que hayas puesto) de `settings.json` y elimina el contador:

```powershell
Remove-Item "$env:APPDATA\dicta\sessions.count"    # Windows
```
```bash
rm ~/Library/Application\ Support/dicta/sessions.count   # macOS
```

---

## 6. Verificación

Recorre esta lista después de instalar. Cada punto dice qué debe pasar.

**1. La suite de tests pasa**

```powershell
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```
```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

Los tests usan dobles de prueba para el micrófono, la GPU y la red, así que no
necesitan hardware ni conexión.

| Rama | Resultado esperado |
|---|---|
| `main` (Windows) | `106 passed` |
| `mac` (macOS) | `55 passed, 10 failed` — ver abajo |

> **En la rama `mac`, 10 tests fallan y es esperado.** El port movió los imports de
> win32 dentro de las funciones para que el módulo cargue en macOS, pero
> `test_injector.py` (3 tests) y `test_docking.py` (7) siguen parcheando esos
> símbolos a nivel de módulo y ya no los encuentran. Es una laguna de la suite, no
> un problema de tu instalación. Para ver solo lo que sí aplica:
>
> ```bash
> .venv/bin/python -m pytest --ignore=tests/test_injector.py --ignore=tests/test_docking.py
> ```

Cualquier otro fallo sí indica que el entorno está mal instalado.

**2. El micrófono se ve**

```powershell
.venv\Scripts\python -c "import sounddevice; print(sounddevice.query_devices())"
```

Debe listar al menos un dispositivo de entrada (con canales de entrada > 0) y
marcar el predeterminado.

**3. dicta arranca y sabe dónde corre**

```powershell
.venv\Scripts\python -m dicta
```

En la consola: `Cargando modelo …` y después `Modelo listo en cuda.` (o `cpu`).
El widget aparece en pantalla.

**4. Instancia única**

Con dicta ya corriendo, lánzala otra vez en otra consola. Debe salir de inmediato
con:

```
dicta ya está corriendo.
```

**5. Ciclo de dictado por click**

Click en el widget → pitido → habla una frase → click otra vez → el texto aparece
en la ventana que tenías activa, **sin** pulsar Enter.

**6. Manos libres**

Di *"Claude"* → pitido → habla → cállate ~2 s → el texto se pega en la terminal **y
se envía** con Enter.

**7. El portapapeles se respeta**

Copia `AAA`, dicta cualquier cosa, y luego pulsa Ctrl+V (o Cmd+V): debe volver a
pegar `AAA`. dicta usa el portapapeles de paso y restaura lo que hubiera.

Para una verificación más exhaustiva (comportamiento del widget, orden de ventanas,
degradación ante fallos) está [`docs/manual-test-checklist.md`](docs/manual-test-checklist.md).

---

## 7. Problemas frecuentes

### `Modelo listo en cpu.` teniendo GPU NVIDIA

Antes de eso la consola habrá impreso `CUDA no disponible (...); usando CPU int8.`
Causas, por orden de probabilidad:

1. Faltan las wheels de CUDA → `.venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`
2. El driver de NVIDIA es viejo. Compruébalo con `nvidia-smi`: la esquina superior
   derecha indica la versión de CUDA que soporta el driver, y debe ser 12.x (12.8+
   en RTX serie 50).
3. Python de 32 bits. `python -c "import platform; print(platform.architecture())"`
   debe decir `64bit`.

El mensaje entre paréntesis es el error real de CTranslate2 y suele nombrar la DLL
que falta.

### `dicta ya está corriendo.` pero no se ve el widget

La unicidad la garantiza un mutex global de Windows, así que hay un proceso vivo
aunque no lo veas (por ejemplo lanzado por los hooks con la ventana oculta).
Ciérralo:

```powershell
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process
Remove-Item "$env:APPDATA\dicta\dicta.pid" -ErrorAction SilentlyContinue
```

> **Ver dos procesos `pythonw` con `-m dicta` es normal**, no son dos instancias.
> El ejecutable del entorno virtual es un redirector que lanza el Python real.

### `No se pudo pegar; la transcripción está en el clipboard.`

La transcripción salió bien; lo que falló fue pegarla. **El texto está en el
portapapeles**: pégalo tú con Ctrl+V. Motivos habituales:

- La ventana de destino se cerró mientras se transcribía.
- Otra aplicación tenía el portapapeles bloqueado en ese instante.
- El atajo de tu terminal no es Ctrl+V → ajusta `paste_shortcut`.

### El texto se pega en la aplicación equivocada

En el modo click, dicta pega en la **última ventana activa** antes de pulsar el
widget. En manos libres pega siempre en la terminal, a propósito: un Enter
automático en otra aplicación sería peligroso.

### El wake word salta solo

Sube `confianza` hacia `1.0` en `[manos_libres]`. Si en cambio te cuesta que te
oiga, bájala. Para ver en vivo qué reconoce y con qué confianza, y calibrar el
umbral con datos, hay un banco de pruebas:

```powershell
.venv\Scripts\python tests\manual_wakeword_live.py
```

En reuniones largas, lo práctico es apagar manos libres desde el click derecho.

### El wake word no arranca

Consola: `Wake word no disponible: ...`. dicta apaga el modo sola y el dictado por
click sigue funcionando. Suele ser que falta `vosk` (en macOS es un extra aparte,
ver [§3.3](#33-manos-libres-opcional)) o que falló la descarga del modelo. Para
reintentar la descarga, borra la carpeta y reinicia:

```powershell
Remove-Item -Recurse "$env:APPDATA\dicta\models"
```

### `Error de micrófono: ...`

El dispositivo no está disponible. Comprueba que aparece en el punto 2 de
[§6](#6-verificación), que ninguna otra aplicación lo tiene en exclusiva, y en
Windows que el micrófono está permitido en *Configuración → Privacidad y seguridad
→ Micrófono*. El widget se queda en error (círculo rojo); un click lo recupera.

### El atajo global no hace nada

Con `[hotkey] enabled = true`, dicta usa la librería `keyboard`, que engancha el
teclado a bajo nivel. En Windows, si la ventana en la que quieres usarlo se ejecuta
**como administrador**, el atajo no llegará a menos que dicta también corra
elevada. Es una restricción del sistema, no del programa. Alternativa: usa el click
en el widget.

### `config.toml inválido (...); usando defaults.`

Error de sintaxis en el TOML. dicta arranca con los valores por defecto. Compara tu
archivo con [`config.example.toml`](config.example.toml); lo más común es una coma
de más en una lista o comillas sin cerrar.

### El widget no sigue a la terminal

En Windows debería anclarse a la esquina inferior derecha de la terminal y seguirla.
Arrástralo una vez para fijar el desplazamiento que quieras; se recuerda. **En macOS
esto no está implementado todavía** ([§3.6](#36-limitaciones-conocidas-del-port-de-macos)).

Para reiniciar la posición desde cero, borra el estado guardado:

```powershell
Remove-Item "$env:APPDATA\dicta\state.json"
```

### El pip falla al instalar

Comprueba que el Python del entorno virtual es 3.11–3.13 de 64 bits:

```powershell
.venv\Scripts\python -c "import sys, platform; print(sys.version, platform.architecture())"
```

Todas las dependencias tienen wheels precompiladas para esas versiones en Windows y
macOS: si pip intenta **compilar** algo, es señal de que la versión de Python o la
arquitectura no encajan.

---

## 8. Desinstalar

dicta no toca el registro ni instala servicios. Para quitarla del todo:

1. Cierra dicta (click derecho → Salir).
2. Borra los bloques de hooks de `~/.claude/settings.json`, si los pusiste.
3. Borra la carpeta de datos:
   ```powershell
   Remove-Item -Recurse "$env:APPDATA\dicta"                      # Windows
   ```
   ```bash
   rm -rf ~/Library/Application\ Support/dicta                    # macOS
   ```
4. Borra el clon del repositorio (incluye el entorno virtual).
5. Opcional: los modelos de Whisper están en la caché compartida de Hugging Face,
   `~/.cache/huggingface/hub`. Bórrala solo si no la usa ninguna otra herramienta.
