# Checklist de verificación manual (desktop, RTX 5070)

Entorno: Windows 11 x64, venv con deps completas, micrófono conectado.

## Arranque
- [ ] `python -m dicta` arranca, consola muestra "Cargando modelo…" y luego "Modelo listo en cuda"
- [ ] Primera vez: descarga del modelo visible en consola
- [ ] Widget aparece abajo a la derecha, barras grises respirando (cargando) → onda lenta terracota (armado) o barras quietas (reposo)
- [ ] Segunda instancia (`python -m dicta` en otra consola) sale inmediatamente con "dicta ya está corriendo."

## Ciclo de dictado
- [ ] Click → beep agudo, cápsula terracota con barras
- [ ] Hablar una frase en español → click → beep grave, cápsula tinta con puntos → texto pegado en la terminal activa
- [ ] El texto NO se envía con Enter automático (eso es solo del modo manos libres)
- [ ] Spanglish técnico: "haz commit y push al branch de Netlify y corre el deploy" se transcribe con los términos correctos
- [ ] Click durante transcripción: ignorado
- [ ] Dictar silencio (no hablar): beep de error, no se pega nada
- [ ] Clipboard: copiar "AAA" antes de dictar → tras dictar, Ctrl+V pega "AAA" otra vez

## Widget
- [ ] Arrastrar el widget → soltar NO dispara dictado
- [ ] Cerrar y reabrir dicta → widget aparece donde lo dejaste
- [ ] Click derecho → Salir funciona

## Manos libres (wake word)
- [ ] Primera vez: consola muestra la descarga del modelo Vosk (~39 MB)
- [ ] Widget en onda lenta (armado) → decir "Claude" → ding → cápsula escuchando
- [ ] Las barras de la cápsula se mueven al hablar y caen al callar
- [ ] Hablar y callar ~2 s → transcribe → el texto aparece en la terminal Y SE ENVÍA (Enter)
- [ ] Dictado por click (no wake word) → el texto NO se envía (sin Enter)
- [ ] Decir "Claude" y no hablar → a los ~10 s beep suave y vuelve a armado (no pega nada)
- [ ] Decir "Claude" durante un dictado en curso → no hace nada
- [ ] Click derecho → desmarcar "Manos libres" → barras quietas (reposo); decir "Claude" no hace nada
- [ ] Volver a marcar "Manos libres" → onda lenta, vuelve a responder
- [ ] Falso positivo: mantener una conversación cerca del micro 1 min sin decir "Claude" → no se dispara

## Z-order (fix botón pegado)
- [ ] Con la terminal delante: el botón se ve pegado a su esquina
- [ ] Tapar la terminal con otra ventana (sin minimizar) → el botón queda DETRÁS (no flota encima)
- [ ] Traer la terminal al frente → el botón emerge con ella
- [ ] Minimizar la terminal → el botón se oculta; restaurar → reaparece

## Hooks
- [ ] Con hooks instalados: abrir `claude` → widget aparece solo
- [ ] Abrir segunda sesión de `claude` → sigue una sola instancia del widget
- [ ] Cerrar una sesión → widget sigue; cerrar la última → widget desaparece en ~2 s
- [ ] Lanzado a mano (sin counter file): no se auto-cierra nunca

## Degradación
- [ ] Renombrar temporalmente las DLLs de CUDA (o forzar fallo) → arranca en CPU con aviso en consola
- [ ] Desconectar micrófono y hacer click → widget en error (círculo rojo con !), click lo recupera
- [ ] Cerrar la terminal destino antes de que termine la transcripción → beep de error, texto queda en clipboard

## v3 — voz de salida

- [ ] Respuesta de Claude que termina en pregunta → dicta la lee → ding →
      contestas → aparece en la terminal con Enter.
- [ ] Respuesta sin pregunta → dicta lee el cierre y vuelve a reposo sin abrir mic.
- [ ] Aviso de permiso → lo lee, NO abre mic.
- [ ] Click durante la lectura corta la voz y abre escucha.
- [ ] El TTS diciendo "Claude" no dispara el wake word.
- [ ] Check "Voz" del menú apaga/enciende al vuelo.
- [ ] Validar la voz ef_dora con los oídos de Robert; si no convence, plan B Piper.
