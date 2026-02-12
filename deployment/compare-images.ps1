# Docker Security Improvement Comparison Script
# Run this to compare original vs optimized images

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Docker Image Security Comparison" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Function to build and scan image
function Test-DockerImage {
    param(
        [string]$ImageName,
        [string]$DockerfilePath,
        [string]$Label
    )
    
    Write-Host "Building $Label..." -ForegroundColor Yellow
    docker build -t $ImageName -f $DockerfilePath ../../
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Build successful" -ForegroundColor Green
        
        # Get image size
        $size = docker images $ImageName --format "{{.Size}}"
        Write-Host "  Image Size: $size" -ForegroundColor Cyan
        
        # Count layers
        $layers = (docker history $ImageName --format "{{.ID}}" | Measure-Object).Count
        Write-Host "  Layers: $layers" -ForegroundColor Cyan
        
        # Run Snyk scan if available
        Write-Host "  Running security scan..." -ForegroundColor Yellow
        $snykOutput = snyk container test $ImageName --json 2>&1
        
        if ($LASTEXITCODE -eq 0 -or $snykOutput) {
            try {
                $snykJson = $snykOutput | ConvertFrom-Json
                $vulnCount = $snykJson.uniqueCount
                $critical = ($snykJson.vulnerabilities | Where-Object { $_.severity -eq "critical" }).Count
                $high = ($snykJson.vulnerabilities | Where-Object { $_.severity -eq "high" }).Count
                $medium = ($snykJson.vulnerabilities | Where-Object { $_.severity -eq "medium" }).Count
                $low = ($snykJson.vulnerabilities | Where-Object { $_.severity -eq "low" }).Count
                
                Write-Host "  Vulnerabilities:" -ForegroundColor Cyan
                Write-Host "    Critical: $critical" -ForegroundColor $(if ($critical -gt 0) { "Red" } else { "Green" })
                Write-Host "    High: $high" -ForegroundColor $(if ($high -gt 0) { "Red" } else { "Yellow" })
                Write-Host "    Medium: $medium" -ForegroundColor Yellow
                Write-Host "    Low: $low" -ForegroundColor Gray
                Write-Host "    Total: $vulnCount" -ForegroundColor Cyan
            } catch {
                Write-Host "  ⚠ Could not parse Snyk output" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  ⚠ Snyk not available or scan failed" -ForegroundColor Yellow
        }
    } else {
        Write-Host "✗ Build failed" -ForegroundColor Red
    }
    
    Write-Host ""
}

# Check if Snyk is installed
Write-Host "Checking prerequisites..." -ForegroundColor Yellow
$snykInstalled = Get-Command snyk -ErrorAction SilentlyContinue
if (-not $snykInstalled) {
    Write-Host "⚠ Snyk CLI not found. Install with: npm install -g snyk" -ForegroundColor Yellow
    Write-Host "  Continuing without vulnerability scanning..." -ForegroundColor Yellow
    Write-Host ""
}

# Test original image
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "1. Testing ORIGINAL Dockerfile" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Test-DockerImage -ImageName "o2ai-backend-original" `
                 -DockerfilePath "deployment/backend/Dockerfile" `
                 -Label "Original Image"

# Test optimized image
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "2. Testing OPTIMIZED Dockerfile" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Test-DockerImage -ImageName "o2ai-backend-optimized" `
                 -DockerfilePath "deployment/backend/Dockerfile.optimized" `
                 -Label "Optimized Image"

# Summary
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Comparison Summary" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

$originalSize = docker images o2ai-backend-original --format "{{.Size}}"
$optimizedSize = docker images o2ai-backend-optimized --format "{{.Size}}"

Write-Host "Original Image:  $originalSize" -ForegroundColor Yellow
Write-Host "Optimized Image: $optimizedSize" -ForegroundColor Green
Write-Host ""

Write-Host "Key Improvements:" -ForegroundColor Cyan
Write-Host "  ✓ Multi-stage build removes build tools" -ForegroundColor Green
Write-Host "  ✓ Debian Bookworm (stable) base image" -ForegroundColor Green
Write-Host "  ✓ Smaller attack surface" -ForegroundColor Green
Write-Host "  ✓ Reduced image size" -ForegroundColor Green
Write-Host "  ✓ .dockerignore prevents sensitive files" -ForegroundColor Green
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Review the optimized Dockerfile" -ForegroundColor White
Write-Host "  2. Test the optimized image in your environment" -ForegroundColor White
Write-Host "  3. If tests pass, replace Dockerfile with Dockerfile.optimized" -ForegroundColor White
Write-Host "  4. Set up monthly image rebuilds" -ForegroundColor White
Write-Host ""

Write-Host "To use the optimized image:" -ForegroundColor Cyan
Write-Host "  mv deployment/backend/Dockerfile deployment/backend/Dockerfile.old" -ForegroundColor Gray
Write-Host "  mv deployment/backend/Dockerfile.optimized deployment/backend/Dockerfile" -ForegroundColor Gray
Write-Host "  docker-compose build --no-cache" -ForegroundColor Gray
Write-Host ""
