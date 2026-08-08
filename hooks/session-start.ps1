# Incrementa el contador de sesiones y lanza dicta si no está corriendo.
$dir = Join-Path $env:APPDATA "dicta"
New-Item -ItemType Directory -Force $dir | Out-Null

$counterFile = Join-Path $dir "sessions.count"
$n = 0
if (Test-Path $counterFile) {
    try { $n = [int](Get-Content $counterFile -Raw).Trim() } catch { $n = 0 }
}
Set-Content $counterFile ($n + 1)

$pidFile = Join-Path $dir "dicta.pid"
$running = $false
if (Test-Path $pidFile) {
    try {
        $dictaPid = [int](Get-Content $pidFile -Raw).Trim()
        $running = $null -ne (Get-Process -Id $dictaPid -ErrorAction SilentlyContinue)
    } catch { $running = $false }
}

if (-not $running) {
    # El repo es la carpeta que contiene a hooks\: no hay nada que ajustar a mano.
    $repo = Split-Path -Parent $PSScriptRoot
    $pythonw = Join-Path $repo ".venv\Scripts\pythonw.exe"
    Start-Process -WindowStyle Hidden $pythonw -ArgumentList "-m", "dicta" -WorkingDirectory $repo
}
