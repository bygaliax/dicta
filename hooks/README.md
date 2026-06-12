# Hooks de Claude Code

Añade esto a `~/.claude/settings.json` en el desktop (ajusta las rutas al clon real):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\proyectos\\dicta\\hooks\\session-start.ps1\""
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\proyectos\\dicta\\hooks\\session-end.ps1\""
          }
        ]
      }
    ]
  }
}
```

Cómo funciona: cada sesión de Claude Code incrementa `%APPDATA%\dicta\sessions.count`
al abrir y lo decrementa al cerrar. dicta lo revisa cada 2 s y se cierra al llegar a 0.
Si lanzas dicta a mano (sin hooks), el contador no existe y dicta nunca se auto-cierra.
