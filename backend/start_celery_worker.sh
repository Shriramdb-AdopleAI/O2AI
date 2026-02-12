#!/bin/bash
# Start Celery worker for parallel document processing

echo "Starting Celery worker..."
echo "========================================"

cd backend

# Check if Redis is running
echo "Checking Redis connection..."
if ! python -c "import redis; redis.Redis.from_url('redis://localhost:6379/0').ping()" 2>/dev/null; then
    echo "ERROR: Redis is not running!"
    echo "Please start Redis before starting Celery worker."
    echo "Install Redis from: https://redis.io/download"
    echo "Or use Docker: docker run -d -p 6379:6379 redis"
    exit 1
fi

echo "Redis connection OK!"

# Start Celery worker with prefork pool for Unix/Linux
# On Windows, use: --pool=solo instead
celery -A core.celery_app worker --loglevel=info --pool=prefork --concurrency=10 --queues=processing

