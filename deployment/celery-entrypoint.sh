#!/bin/bash
# Simplified Celery entrypoint script
# Runs Celery worker with proper configuration

set -e

echo "Starting Celery worker..."
echo "Redis URL: ${REDIS_URL}"
echo "Working directory: $(pwd)"

# Ensure data directory exists and has proper permissions
mkdir -p /app/backend/data /app/logs
chmod -R 777 /app/backend/data /app/logs

# Create log files if they don't exist
touch /app/logs/ocr_processing.log /app/backend/ocr_processing.log
chmod 666 /app/logs/ocr_processing.log /app/backend/ocr_processing.log

# Run celery worker
exec celery -A core.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --concurrency=4 \
    --queues=processing \
    --uid=1000 \
    --gid=1000
