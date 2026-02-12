#!/bin/sh
# Redis entrypoint script to ensure it runs as a writable master instance

set -e

# Start Redis in background
redis-server --appendonly yes &
REDIS_PID=$!

# Wait for Redis to be ready
echo "Waiting for Redis to start..."
for i in $(seq 1 30); do
    if redis-cli ping > /dev/null 2>&1; then
        echo "Redis is ready!"
        break
    fi
    sleep 1
done

# Ensure Redis is configured as master (not replica)
echo "Configuring Redis as master..."
redis-cli SLAVEOF NO ONE

# Ensure Redis is writable (not read-only)
echo "Ensuring Redis is writable..."
redis-cli CONFIG SET slave-read-only no

# Verify configuration
ROLE=$(redis-cli INFO replication | grep "^role:" | cut -d: -f2 | tr -d '\r\n')
echo "Redis role: $ROLE"

if [ "$ROLE" != "master" ]; then
    echo "ERROR: Redis is not configured as master!"
    exit 1
fi

echo "Redis is configured as writable master. Ready to accept connections."

# Wait for Redis process
wait $REDIS_PID

