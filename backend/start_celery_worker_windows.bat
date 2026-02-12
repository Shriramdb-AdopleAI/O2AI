@echo off
REM Start multiple Celery workers on Windows using threads pool for better parallel processing

echo Starting Celery worker on Windows...
echo ========================================

cd backend

REM Check if Redis is running
echo Checking Redis connection...
python -c "import redis; redis.Redis.from_url('redis://localhost:6379/0').ping()" 2>NUL
if errorlevel 1 (
    echo ERROR: Redis is not running!
    echo Please start Redis before starting Celery worker.
    echo Install Redis from: https://redis.io/download
    echo Or use Docker: docker run -d -p 6379:6379 redis
    pause
    exit /b 1
)

echo Redis connection OK!
echo.
echo Starting Celery worker with threads pool...
echo.
echo NOTE: On Windows, prefork pool causes permission errors.
echo Using threads pool for parallel processing instead.
echo.

REM Start Celery worker with threads pool (better for Windows)
celery -A core.celery_app worker --loglevel=info --pool=threads --concurrency=10 --queues=processing

pause

