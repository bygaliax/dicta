# Hooks de Claude Code

Con estos hooks, dicta arranca sola al abrir `claude` y se cierra al salir de la
última sesión.

Los scripts **deducen solos la ruta del repositorio** a partir de su propia
ubicación: no hay que editarlos. Lo único que tienes que poner es la ruta real de
tu clon dentro de `~/.claude/settings.json`.

## Windows

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
    ]
  }
}
```

Sustituye `C:\\ruta\\a\\dicta` por la ruta de tu clon. Las barras invertidas van
dobladas porque en JSON son un carácter de escape.

En macOS se usan los `.sh` equivalentes de la rama `mac`; ver
[`INSTALL.md`](../INSTALL.md#5-hooks-de-claude-code-arranque-automático).

## Cómo funciona

Cada sesión de Claude Code incrementa `%APPDATA%\dicta\sessions.count` al abrir y
lo decrementa al cerrar. dicta lo revisa cada 2 s y se cierra al llegar a 0.

Si lanzas dicta a mano (sin hooks), el contador no existe y dicta nunca se
auto-cierra.
