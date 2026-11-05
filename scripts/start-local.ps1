$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno Python gratuito..." -ForegroundColor Cyan
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { py -m venv .venv }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

$secretsFile = ".local-secrets.ps1"
if (-not (Test-Path $secretsFile)) {
    $platform = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
    $admin = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
    $lines = @(
        '$env:BOOKING_PLATFORM_TOKEN = "' + $platform + '"',
        '$env:BOOKING_ADMIN_TOKEN = "' + $admin + '"',
        '$env:BOOKING_DB_PATH = "bookings.db"'
    )
    Set-Content -Path $secretsFile -Value $lines -Encoding UTF8
}
. .\$secretsFile

Write-Host ""
Write-Host "AUREN Booking Engine listo para iniciar." -ForegroundColor Green
Write-Host "Cliente: http://127.0.0.1:8000/web/"
Write-Host "Admin:   http://127.0.0.1:8000/web/admin.html"
Write-Host "API:     http://127.0.0.1:8000/docs"
Write-Host "Token admin local (no compartir): $env:BOOKING_ADMIN_TOKEN" -ForegroundColor Yellow
Write-Host "Para detenerlo: Ctrl + C"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
