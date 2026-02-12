#!/bin/sh
# Redis startup script to ensure it runs as a writable master instance

# Start Redis server
exec redis-server --appendonly yes

