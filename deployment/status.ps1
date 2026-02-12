# Service Status Script
# This script shows the status of all Docker services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "O2AI Fax Automation - Service Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to deployment directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "Service Status:" -ForegroundColor Yellow
Write-Host ""
docker-compose ps

Write-Host ""
Write-Host "Container Resource Usage:" -ForegroundColor Yellow
Write-Host ""
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

Write-Host ""
Write-Host "Service Health:" -ForegroundColor Yellow
Write-Host ""

# Check each service health
$services = @("ocr-redis", "ocr-backend", "ocr-celery", "ocr-frontend")

foreach ($service in $services) {
    $health = docker inspect --format='{{.State.Health.Status}}' $service 2>$null
    if ($LASTEXITCODE -eq 0) {
        if ($health -eq "healthy") {
            Write-Host "  ✓ $service : $health" -ForegroundColor Green
        } elseif ($health -eq "starting") {
            Write-Host "  ⟳ $service : $health" -ForegroundColor Yellow
        } else {
            Write-Host "  ✗ $service : $health" -ForegroundColor Red
        }
    } else {
        $status = docker inspect --format='{{.State.Status}}' $service 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  • $service : $status (no health check)" -ForegroundColor Cyan
        } else {
            Write-Host "  ✗ $service : not found" -ForegroundColor Red
        }
    }
}

Write-Host ""
