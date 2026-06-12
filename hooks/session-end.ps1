# Decrementa el contador; dicta se auto-cierra cuando lo ve en 0.
$counterFile = Join-Path $env:APPDATA "dicta\sessions.count"
if (Test-Path $counterFile) {
    $n = 0
    try { $n = [int](Get-Content $counterFile -Raw).Trim() } catch { $n = 0 }
    Set-Content $counterFile ([Math]::Max(0, $n - 1))
}
