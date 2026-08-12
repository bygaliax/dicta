# Al terminar cada respuesta de Claude, encola el texto para que dicta lea
# el cierre. Usa last_assistant_message; si el CLI no lo trae (versiones
# viejas), cae al transcript JSONL. Nunca bloquea ni falla.
$ErrorActionPreference = "SilentlyContinue"
try {
    $p = [Console]::In.ReadToEnd() | ConvertFrom-Json
} catch { exit 0 }
$text = [string]$p.last_assistant_message
if (-not $text -and $p.transcript_path -and (Test-Path $p.transcript_path)) {
    $lines = @(Get-Content $p.transcript_path -Tail 200)
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        try { $o = $lines[$i] | ConvertFrom-Json } catch { continue }
        if ($o.type -eq "assistant" -and $o.message.content) {
            $text = ($o.message.content | Where-Object { $_.type -eq "text" } |
                ForEach-Object { $_.text }) -join "`n"
            if ($text) { break }
        }
    }
}
if (-not $text) { exit 0 }
# dicta solo lee el ultimo parrafo: con la cola del texto sobra.
if ($text.Length -gt 4000) { $text = $text.Substring($text.Length - 4000) }
$dir = Join-Path $env:APPDATA "dicta\speak"
New-Item -ItemType Directory -Force $dir | Out-Null
$ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
@{ ts = $ts; kind = "cierre"; text = $text } | ConvertTo-Json -Compress |
    Set-Content -Encoding utf8 (Join-Path $dir "$ts-cierre.json")
exit 0
