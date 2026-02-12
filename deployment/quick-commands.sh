#!/usr/bin/env bash
# Quick Commands for Merged Backend Container

echo "==================================="
echo "Backend Container Quick Commands"
echo "==================================="
echo ""

# Build and start
echo "📦 Build and Start:"
echo "  docker-compose up --build -d"
echo ""

# View all logs
echo "📋 View All Logs:"
echo "  docker logs -f backend"
echo ""

# View individual service logs
echo "📝 View Individual Service Logs:"
echo "  docker exec backend tail -f /app/logs/backend.log"
echo "  docker exec backend tail -f /app/logs/celery.log"
echo "  docker exec backend tail -f /app/logs/redis.log"
echo "  docker exec backend tail -f /app/logs/supervisord.log"
echo ""

# Check service status
echo "✅ Check Service Status:"
echo "  docker exec backend supervisorctl status"
echo ""

# Restart services
echo "🔄 Restart Individual Services:"
echo "  docker exec backend supervisorctl restart backend"
echo "  docker exec backend supervisorctl restart celery"
echo "  docker exec backend supervisorctl restart redis"
echo ""

# Test Redis
echo "🔍 Test Redis Connection:"
echo "  docker exec backend redis-cli ping"
echo ""

# Test Backend API
echo "🌐 Test Backend API:"
echo "  curl http://localhost:8001/api/v1/health"
echo ""

# Stop and remove
echo "🛑 Stop and Remove:"
echo "  docker-compose down"
echo ""

# View container stats
echo "📊 View Container Stats:"
echo "  docker stats backend"
echo ""

# Enter container shell
echo "💻 Enter Container Shell:"
echo "  docker exec -it backend bash"
echo ""

echo "==================================="
