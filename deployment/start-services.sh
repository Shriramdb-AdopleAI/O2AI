#!/bin/bash
# Script to start all services in the correct order

set -e

echo "Starting O2AI Fax Automation services..."

cd "$(dirname "$0")"

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose down

# Start Redis first
echo "Starting Redis..."
docker-compose up -d redis

# Wait for Redis to be healthy
echo "Waiting for Redis to be healthy..."
timeout=60
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if docker-compose ps redis | grep -q "healthy"; then
        echo "Redis is healthy!"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

if [ $elapsed -ge $timeout ]; then
    echo "ERROR: Redis did not become healthy within $timeout seconds"
    docker-compose logs redis
    exit 1
fi

# Start backend
echo "Starting backend..."
docker-compose up -d backend

# Wait for backend to be healthy
echo "Waiting for backend to be healthy..."
timeout=90
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if docker-compose ps backend | grep -q "healthy"; then
        echo "Backend is healthy!"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

# Start Celery and frontend
echo "Starting Celery and frontend..."
docker-compose up -d celery frontend

# Show status
echo ""
echo "All services started! Status:"
docker-compose ps

echo ""
echo "Services are available at:"
echo "  - Frontend: http://localhost:8080"
echo "  - Backend API: http://localhost:8001"
echo "  - Redis: localhost:6379"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop services: docker-compose down"
