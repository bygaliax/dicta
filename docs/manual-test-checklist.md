# Checklist de verificación manual (desktop, RTX 5060)

Entorno: Windows 11 x64, venv con deps completas, micrófono conectado.

## Arranque
- [ ] `python -m dicta` arranca, consola muestra "Cargando modelo…" y luego "Modelo listo en cuda"
- [ ] Primera vez: descarga del modelo visible en consola
- [ ] Widget aparece abajo a la derecha, gris (cargando) → azul 📞 (listo)
- [ ] Segunda instancia (`python -m dicta` en otra consola) sale inmediatamente con "dicta ya está corriendo."

## Ciclo de dictado
- [ ] Click → beep agudo, widget rojo 🎙
- [ ] Hablar una frase en español → click → beep grave, widget naranja ✍ → texto pegado en la terminal activa
- [ ] El texto NO se envía (no hay Enter automático)
- [ ] Spanglish técnico: "haz commit y push al branch de Netlify y corre el deploy" se transcribe con los términos correctos
- [ ] Click durante transcripción: ignorado
- [ ] Dictar silencio (no hablar): beep de error, no se pega nada
- [ ] Clipboard: copiar "AAA" antes de dictar → tras dictar, Ctrl+V pega "AAA" otra vez

## Widget
- [ ] Arrastrar el widget → soltar NO dispara dictado
- [ ] Cerrar y reabrir dicta → widget aparece donde lo dejaste
- [ ] Click derecho → Salir funciona

## Hooks
- [ ] Con hooks instalados: abrir `claude` → widget aparece solo
- [ ] Abrir segunda sesión de `claude` → sigue una sola instancia del widget
- [ ] Cerrar una sesión → widget sigue; cerrar la última → widget desaparece en ~2 s
- [ ] Lanzado a mano (sin counter file): no se auto-cierra nunca

## Degradación
- [ ] Renombrar temporalmente las DLLs de CUDA (o forzar fallo) → arranca en CPU con aviso en consola
- [ ] Desconectar micrófono y hacer click → widget en error ⚠, click lo recupera
- [ ] Cerrar la terminal destino antes de que termine la transcripción → beep de error, texto queda en clipboard
