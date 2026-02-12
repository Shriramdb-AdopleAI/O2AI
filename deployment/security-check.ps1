# Security Status Check Script
# Quick verification of Docker security improvements

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Docker Security Status Check" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "❌ Error: docker-compose.yml not found" -ForegroundColor Red
    Write-Host "   Please run this script from the deployment directory" -ForegroundColor Yellow
    exit 1
}

# 1. Container Health Status
Write-Host "1. Container Health Status" -ForegroundColor Yellow
Write-Host "   " -NoNewline
$containers = docker-compose ps --format json | ConvertFrom-Json

$allHealthy = $true
foreach ($container in $containers) {
    $status = if ($container.Health -eq "healthy" -or $container.State -eq "running") { "✅" } else { "❌"; $allHealthy = $false }
    Write-Host "$status $($container.Name): $($container.Health)" -ForegroundColor $(if ($container.Health -eq "healthy") { "Green" } else { "Yellow" })
}
Write-Host ""

# 2. Image Sizes
Write-Host "2. Docker Image Sizes" -ForegroundColor Yellow
$images = @("o2ai-fax-automation-backend", "o2ai-fax-automation-celery", "o2ai-fax-automation-frontend")
foreach ($img in $images) {
    $size = docker images $img --format "{{.Size}}"
    if ($size) {
        Write-Host "   📦 $img`: $size" -ForegroundColor Cyan
    }
}
Write-Host ""

# 3. Security Features Check
Write-Host "3. Security Features Implemented" -ForegroundColor Yellow

# Check for .dockerignore
if (Test-Path "backend/.dockerignore") {
    Write-Host "   ✅ .dockerignore file present" -ForegroundColor Green
} else {
    Write-Host "   ❌ .dockerignore file missing" -ForegroundColor Red
}

# Check Dockerfile for multi-stage build
$dockerfile = Get-Content "backend/Dockerfile" -Raw
if ($dockerfile -match "AS builder" -and $dockerfile -match "AS runtime") {
    Write-Host "   ✅ Multi-stage build enabled" -ForegroundColor Green
} else {
    Write-Host "   ❌ Multi-stage build not detected" -ForegroundColor Red
}

# Check for stable base image
if ($dockerfile -match "bookworm") {
    Write-Host "   ✅ Using Debian Bookworm (stable)" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Not using Debian Bookworm stable" -ForegroundColor Yellow
}

# Check docker-compose health check
$compose = Get-Content "docker-compose.yml" -Raw
if ($compose -match 'curl.*--fail.*health') {
    Write-Host "   ✅ Health check using curl" -ForegroundColor Green
} elseif ($compose -match 'wget.*health') {
    Write-Host "   ❌ Health check still using wget (should be curl)" -ForegroundColor Red
} else {
    Write-Host "   ⚠️  Health check configuration unclear" -ForegroundColor Yellow
}

Write-Host ""

# 4. Application Accessibility
Write-Host "4. Application Accessibility" -ForegroundColor Yellow

# Test backend
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/api/v1/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Backend API: Accessible (http://localhost:8001)" -ForegroundColor Green
    }
} catch {
    Write-Host "   ❌ Backend API: Not accessible" -ForegroundColor Red
}

# Test frontend
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Frontend: Accessible (http://localhost:8080)" -ForegroundColor Green
    }
} catch {
    Write-Host "   ❌ Frontend: Not accessible" -ForegroundColor Red
}

Write-Host ""

# 5. Build Tools Check (should NOT be in runtime)
Write-Host "5. Runtime Security Check" -ForegroundColor Yellow
Write-Host "   Checking if build tools are removed from runtime..." -ForegroundColor Gray

$buildTools = @("gcc", "g++", "make")
$foundBuildTools = $false

foreach ($tool in $buildTools) {
    try {
        $result = docker exec ocr-backend which $tool 2>&1
        if ($result -notmatch "not found" -and $result -match "/") {
            Write-Host "   ⚠️  Found $tool in runtime (should be removed)" -ForegroundColor Yellow
            $foundBuildTools = $true
        }
    } catch {
        # Tool not found - this is good
    }
}

if (-not $foundBuildTools) {
    Write-Host "   ✅ Build tools successfully removed from runtime" -ForegroundColor Green
}

Write-Host ""

# 6. Last Build Date
Write-Host "6. Image Freshness" -ForegroundColor Yellow
$backendImage = docker images o2ai-fax-automation-backend --format "{{.CreatedAt}}"
if ($backendImage) {
    Write-Host "   📅 Backend image created: $backendImage" -ForegroundColor Cyan
    
    # Parse the date and check if it's older than 30 days
    try {
        $createdDate = [DateTime]::Parse($backendImage.Split(' ')[0])
        $daysSinceCreated = ((Get-Date) - $createdDate).Days
        
        if ($daysSinceCreated -gt 30) {
            Write-Host "   ⚠️  Image is $daysSinceCreated days old - consider rebuilding" -ForegroundColor Yellow
        } else {
            Write-Host "   ✅ Image is fresh ($daysSinceCreated days old)" -ForegroundColor Green
        }
    } catch {
        # Could not parse date
    }
}

Write-Host ""

# Summary
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

if ($allHealthy) {
    Write-Host "✅ All containers are healthy" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some containers are not healthy - check logs" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  • Run Snyk scan: snyk container test o2ai-fax-automation-backend" -ForegroundColor White
Write-Host "  • Check logs: docker-compose logs -f" -ForegroundColor White
Write-Host "  • Monthly rebuild: docker-compose build --no-cache --pull" -ForegroundColor White
Write-Host ""

# Optional: Run Snyk scan if available
$snykInstalled = Get-Command snyk -ErrorAction SilentlyContinue
if ($snykInstalled) {
    Write-Host "Snyk CLI detected. Run security scan? (y/n): " -ForegroundColor Yellow -NoNewline
    $response = Read-Host
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host ""
        Write-Host "Running Snyk scan..." -ForegroundColor Cyan
        snyk container test o2ai-fax-automation-backend --severity-threshold=high
    }
} else {
    Write-Host "💡 Tip: Install Snyk CLI for vulnerability scanning" -ForegroundColor Gray
    Write-Host "   npm install -g snyk" -ForegroundColor Gray
}

Write-Host ""
