# Docker Deployment Script for O2AI Fax Automation
# This script builds and starts all Docker services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "O2AI Fax Automation - Docker Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if docker-compose is available
Write-Host "Checking Docker Compose..." -ForegroundColor Yellow
try {
    docker-compose version | Out-Null
    Write-Host "✓ Docker Compose is available" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker Compose is not available. Please install Docker Compose." -ForegroundColor Red
    exit 1
}

# Navigate to deployment directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host ""
Write-Host "Current directory: $scriptPath" -ForegroundColor Cyan

# Check if required files exist
Write-Host ""
Write-Host "Checking required files..." -ForegroundColor Yellow

$requiredFiles = @(
    "docker-compose.yml",
    "env.backend",
    ".env",
    "backend\Dockerfile",
    "frontend\Dockerfile"
)

$allFilesExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✓ $file" -ForegroundColor Green
    } else {
        Write-Host "✗ $file (missing)" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host ""
    Write-Host "Some required files are missing. Please ensure all files are present." -ForegroundColor Red
    exit 1
}

# Stop existing containers
Write-Host ""
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

# Build and start services
Write-Host ""
Write-Host "Building and starting services..." -ForegroundColor Yellow
Write-Host "This may take several minutes on first run..." -ForegroundColor Cyan
Write-Host ""

docker-compose up --build -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Deployment Successful!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Services are starting up. Please wait a moment..." -ForegroundColor Cyan
    Write-Host ""
    
    # Wait for services to be healthy
    Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    # Check service status
    Write-Host ""
    Write-Host "Service Status:" -ForegroundColor Cyan
    docker-compose ps
    
    Write-Host ""
    Write-Host "Access your application:" -ForegroundColor Cyan
    Write-Host "  Frontend:  https://o2ai-fax-automation.centralus.cloudapp.azure.com/" -ForegroundColor White
    Write-Host "  Backend:   http://localhost:8001" -ForegroundColor White
    Write-Host "  API Docs:  http://localhost:8001/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "To view logs, run:" -ForegroundColor Cyan
    Write-Host "  docker-compose logs -f" -ForegroundColor White
    Write-Host ""
    Write-Host "To stop services, run:" -ForegroundColor Cyan
    Write-Host "  docker-compose down" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Deployment Failed!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please check the error messages above." -ForegroundColor Yellow
    Write-Host "To view detailed logs, run:" -ForegroundColor Yellow
    Write-Host "  docker-compose logs" -ForegroundColor White
    Write-Host ""
    exit 1
}
