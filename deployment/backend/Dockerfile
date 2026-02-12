# ============================================
# Multi-Stage Dockerfile for Unified Backend
# Includes: Backend API + Celery Worker + Redis
# Managed by Supervisord
# ============================================

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.12-slim-bookworm AS builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip install --no-cache-dir supervisor

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.12-slim-bookworm AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    REDIS_HOST=localhost \
    REDIS_URL=redis://localhost:6379/0 \
    PATH="/opt/venv/bin:/app/backend:${PATH}"

# Install runtime dependencies including Redis
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    ca-certificates \
    redis-server \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app/backend

# Copy backend application code
COPY backend/ .

# Build arguments for environment variables
ARG AZURE_OPENAI_API_KEY
ARG AZURE_OPENAI_ENDPOINT
ARG OPENAI_API_VERSION
ARG AZURE_OPENAI_DEPLOYMENT
ARG AZURE_STORAGE_CONNECTION_STRING
ARG AZURE_STORAGE_ACCOUNT_URL
ARG AZURE_DOCUMENT_INTELLIGENCE_KEY
ARG AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
ARG EPIC_FHIR_PRIVATE_KEY_PATH
ARG BASE_URL
ARG EPIC_REDIRECT_URI
ARG EPIC_CLIENT_ID
ARG EPIC_AUTHORIZATION_URL
ARG EPIC_TOKEN_URL
ARG EPIC_AUDIENCE
ARG EPIC_SCOPES
ARG EPIC_CLIENT_SECRET
ARG EPIC_FHIR_JWKS_URL
ARG EPIC_FALLBACK_ENCOUNTER_ID
ARG EPIC_FALLBACK_PATIENT_ID
ARG PGHOST
ARG PGUSER
ARG PGPORT
ARG PGDATABASE
ARG PGPASSWORD
ARG EMAIL
ARG REDIS_HOST
ARG REDIS_URL

# Set environment variables
ENV AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
ENV AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
ENV OPENAI_API_VERSION=${OPENAI_API_VERSION}
ENV AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}
ENV AZURE_STORAGE_CONNECTION_STRING=${AZURE_STORAGE_CONNECTION_STRING}
ENV AZURE_STORAGE_ACCOUNT_URL=${AZURE_STORAGE_ACCOUNT_URL}
ENV AZURE_DOCUMENT_INTELLIGENCE_KEY=${AZURE_DOCUMENT_INTELLIGENCE_KEY}
ENV AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=${AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT}
ENV EPIC_FHIR_PRIVATE_KEY_PATH=${EPIC_FHIR_PRIVATE_KEY_PATH}
ENV BASE_URL=${BASE_URL}
ENV EPIC_REDIRECT_URI=${EPIC_REDIRECT_URI}
ENV EPIC_CLIENT_ID=${EPIC_CLIENT_ID}
ENV EPIC_AUTHORIZATION_URL=${EPIC_AUTHORIZATION_URL}
ENV EPIC_TOKEN_URL=${EPIC_TOKEN_URL}
ENV EPIC_AUDIENCE=${EPIC_AUDIENCE}
ENV EPIC_SCOPES=${EPIC_SCOPES}
ENV EPIC_CLIENT_SECRET=${EPIC_CLIENT_SECRET}
ENV EPIC_FHIR_JWKS_URL=${EPIC_FHIR_JWKS_URL}
ENV EPIC_FALLBACK_ENCOUNTER_ID=${EPIC_FALLBACK_ENCOUNTER_ID}
ENV EPIC_FALLBACK_PATIENT_ID=${EPIC_FALLBACK_PATIENT_ID}
ENV PGHOST=${PGHOST}
ENV PGUSER=${PGUSER}
ENV PGPORT=${PGPORT}
ENV PGDATABASE=${PGDATABASE}
ENV PGPASSWORD=${PGPASSWORD}
ENV EMAIL=${EMAIL}
ENV REDIS_HOST=${REDIS_HOST}
ENV REDIS_URL=${REDIS_URL}

# Copy supervisord configuration to proper location
RUN mkdir -p /etc/supervisor/conf.d && \
    cp /app/backend/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create necessary directories with proper structure
RUN mkdir -p \
    /app/backend/data/tenants \
    /app/backend/data/templates \
    /app/backend/data/uploads \
    /app/backend/keys \
    /app/logs \
    /app/redis-data \
    /var/run

# Create log files with proper permissions
RUN touch /app/ocr_processing.log \
    /app/logs/ocr_processing.log \
    /app/backend/ocr_processing.log \
    /app/logs/supervisord.log \
    /app/logs/redis.log \
    /app/logs/redis_error.log \
    /app/logs/backend.log \
    /app/logs/backend_error.log \
    /app/logs/celery.log \
    /app/logs/celery_error.log && \
    chmod -R 666 /app/logs/*.log \
    /app/ocr_processing.log \
    /app/backend/ocr_processing.log

# Set ownership and permissions
RUN chmod -R 755 /app/backend && \
    chmod -R 777 /app/backend/data && \
    chmod -R 777 /app/logs && \
    chmod -R 777 /app/redis-data && \
    chmod 666 /app/ocr_processing.log

# Expose application port and Redis port (for debugging if needed)
EXPOSE 8000 6379

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8000/api/v1/health || exit 1

# Start supervisord to manage all processes
CMD ["/opt/venv/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
