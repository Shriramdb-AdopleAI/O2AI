"""Celery configuration and app instance for asynchronous task processing."""

from celery import Celery
from celery.schedules import crontab
from utility.config import setup_logging
import os
import sys

logger = setup_logging()

# Detect platform
IS_WINDOWS = sys.platform == "win32"

# Redis broker URL (default based on environment)
# For Docker: use 'redis' hostname, for local development: use 'localhost'
# IMPORTANT: Must point to the master/primary Redis instance, NOT a read-only replica
default_redis_host = os.getenv("REDIS_HOST", "localhost")
REDIS_URL = os.getenv("REDIS_URL", f"redis://{default_redis_host}:6379/0")

# Validate Redis URL doesn't point to a replica
# If using Redis Sentinel, the URL should be in format: sentinel://host:port/service_name
if REDIS_URL and "replica" in REDIS_URL.lower():
    logger.warning(f"WARNING: REDIS_URL may point to a replica: {REDIS_URL}")
    logger.warning("Celery requires a writable Redis instance (master/primary), not a replica.")

# Create Celery app
celery_app = Celery(
    "ocr_processor",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["core.celery_tasks"]
)

# Celery configuration
celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    # Task execution settings
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    # Task timeouts
    "task_time_limit": 300,
    "task_soft_time_limit": 270,
    # Task routing
    "task_routes": {
        "core.celery_tasks.process_document": {"queue": "processing"},
        "core.celery_tasks.process_batch_documents": {"queue": "processing"},
        "core.celery_tasks.process_bulk_file": {"queue": "processing"},
        "core.celery_tasks.check_bulk_processing_source": {"queue": "processing"},
    },
    # Worker settings
    "worker_max_tasks_per_child": 100,
    "worker_log_format": "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    "worker_task_log_format": "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s] %(message)s",
    # Result backend settings
    "result_expires": 3600,  # Results expire after 1 hour (3600 seconds)
    "result_backend_always_retry": True,
    "result_backend_max_retries": 10,
    # Redis connection settings - retry on connection errors
    "broker_connection_retry_on_startup": True,
    "broker_connection_retry": True,
    "broker_connection_max_retries": 10,
    "broker_transport_options": {
        "retry_policy": {
            "timeout": 5.0,
            "max_retries": 3,
        },
        "visibility_timeout": 3600,
        "fanout_prefix": True,
        "fanout_patterns": True,
        # Ensure we connect to master, not replica
        "master_name": None,  # Set if using Redis Sentinel
    },
    # Result backend transport options (same as broker)
    "result_backend_transport_options": {
        "retry_policy": {
            "timeout": 5.0,
            "max_retries": 3,
        },
        "master_name": None,  # Set if using Redis Sentinel
    },
}

# Windows-specific configuration
if IS_WINDOWS:
    celery_config.update({
        "worker_pool": "solo",
        "worker_prefetch_multiplier": 1,
    })
    logger.info("Running on Windows - using solo pool (single process)")
else:
    logger.info("Running on Unix/Linux - prefork pool available")

celery_app.conf.update(celery_config)

# Periodic tasks - runs every 5 minutes to check bulk processing/source folder
celery_app.conf.beat_schedule = {
    'check-bulk-processing-source': {
        'task': 'check_bulk_processing_source',  # Task name registered in celery_tasks.py
        'schedule': 300.0,  # Run every 5 minutes (300 seconds)
    },
}

logger.info(f"Celery app initialized with broker: {REDIS_URL}")
logger.info("Bulk processing periodic task scheduled: check_bulk_processing_source (every 5 minutes)")


def check_redis_connection():
    """Check if Redis is available and can be connected to (writable, not read-only replica)."""
    try:
        import redis
        from redis.exceptions import ReadOnlyError, ConnectionError
        
        redis_client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=5, decode_responses=False)
        
        # Test basic connection
        redis_client.ping()
        
        # Test write capability (replicas are read-only)
        test_key = "__redis_write_test__"
        try:
            redis_client.set(test_key, "test", ex=1)  # Set with 1 second expiry
            redis_client.delete(test_key)
            logger.info(f"Redis connection successful (writable): {REDIS_URL}")
            return True
        except ReadOnlyError as e:
            logger.error(f"Redis is read-only replica! Cannot write to: {REDIS_URL}")
            logger.error("Please ensure REDIS_URL points to the master/primary Redis instance, not a replica.")
            logger.error("If using Redis Sentinel, configure it properly to route writes to master.")
            return False
        except Exception as e:
            logger.error(f"Redis write test failed: {REDIS_URL} - Error: {e}")
            return False
            
    except ConnectionError as e:
        logger.error(f"Redis connection failed: {REDIS_URL} - Error: {e}")
        logger.error("Please ensure Redis is running. On Windows, use: docker run -d -p 6379:6379 --name redis redis:latest")
        return False
    except Exception as e:
        logger.error(f"Redis connection failed: {REDIS_URL} - Error: {e}")
        logger.error("Please ensure Redis is running and accessible.")
        return False