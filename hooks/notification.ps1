# Lee la notificacion de Claude Code por stdin y encola el texto para que
# dicta lo hable. Solo pasan los tipos utiles; el resto (auth, MCP) se ignora.
# Nunca bloquea ni falla: sin voz no hay dictado roto.
$ErrorActionPreference = "SilentlyContinue"
try {
    $p = [Console]::In.ReadToEnd() | ConvertFrom-Json
} catch { exit 0 }
$kinds = @{
    "permission_prompt" = "permiso"
    "idle_prompt"       = "aviso"
    "agent_needs_input" = "aviso"
}
$kind = $kinds[[string]$p.notification_type]
$text = [string]$p.message
if (-not $kind -or -not $text) { exit 0 }
$dir = Join-Path $env:APPDATA "dicta\speak"
New-Item -ItemType Directory -Force $dir | Out-Null
$ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
@{ ts = $ts; kind = $kind; text = $text } | ConvertTo-Json -Compress |
    Set-Content -Encoding utf8 (Join-Path $dir "$ts-$kind.json")
exit 0
