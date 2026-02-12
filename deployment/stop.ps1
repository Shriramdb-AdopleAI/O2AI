# Stop Docker Services Script
# This script stops all running Docker services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stopping O2AI Fax Automation Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to deployment directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "Stopping all services..." -ForegroundColor Yellow
docker-compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ All services stopped successfully" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "✗ Failed to stop services" -ForegroundColor Red
    Write-Host ""
    exit 1
}
