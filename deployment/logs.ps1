# View Logs Script
# This script displays logs from all Docker services

param(
    [string]$Service = "",
    [switch]$Follow = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "O2AI Fax Automation - Service Logs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to deployment directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

if ($Service -eq "") {
    Write-Host "Showing logs for all services..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to exit" -ForegroundColor Cyan
    Write-Host ""
    
    if ($Follow) {
        docker-compose logs -f
    } else {
        docker-compose logs --tail=100
    }
} else {
    Write-Host "Showing logs for service: $Service" -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to exit" -ForegroundColor Cyan
    Write-Host ""
    
    if ($Follow) {
        docker-compose logs -f $Service
    } else {
        docker-compose logs --tail=100 $Service
    }
}
