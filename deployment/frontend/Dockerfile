# Build stage
FROM node:20-alpine AS build

WORKDIR /app/frontend

# Install build dependencies for native modules
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    libc6-compat \
    && ln -sf python3 /usr/bin/python

# Copy package files first for better layer caching
COPY frontend/package*.json ./

# Install dependencies with clean install
RUN npm ci --legacy-peer-deps

# Copy frontend source code
COPY frontend/ .

# Build arguments for environment variables
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build the application
RUN npm run build

# Ensure PDF.js worker file is in the dist folder
RUN if [ -f public/pdf.worker.min.mjs ]; then \
      cp public/pdf.worker.min.mjs dist/pdf.worker.min.mjs; \
    fi

# Production stage
FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built assets from build stage
COPY --from=build /app/frontend/dist /usr/share/nginx/html

# Create custom nginx configuration
RUN echo 'server {' > /etc/nginx/conf.d/default.conf && \
    echo '    listen 80;' >> /etc/nginx/conf.d/default.conf && \
    echo '    server_name _;' >> /etc/nginx/conf.d/default.conf && \
    echo '    root /usr/share/nginx/html;' >> /etc/nginx/conf.d/default.conf && \
    echo '    index index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '' >> /etc/nginx/conf.d/default.conf && \
    echo '    # Use Docker internal DNS resolver' >> /etc/nginx/conf.d/default.conf && \
    echo '    resolver 127.0.0.11 valid=30s;' >> /etc/nginx/conf.d/default.conf && \
    echo '' >> /etc/nginx/conf.d/default.conf && \
    echo '    # Security headers for Azure AD authentication' >> /etc/nginx/conf.d/default.conf && \
    echo '    add_header Cross-Origin-Opener-Policy "same-origin-allow-popups" always;' >> /etc/nginx/conf.d/default.conf && \
    echo '    add_header Cross-Origin-Embedder-Policy "unsafe-none" always;' >> /etc/nginx/conf.d/default.conf && \
    echo '' >> /etc/nginx/conf.d/default.conf && \
    echo '    location / {' >> /etc/nginx/conf.d/default.conf && \
    echo '        try_files $uri $uri/ /index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '    }' >> /etc/nginx/conf.d/default.conf && \
    echo '' >> /etc/nginx/conf.d/default.conf && \
    echo '    location /api {' >> /etc/nginx/conf.d/default.conf && \
    echo '        set $backend_upstream http://backend:8000;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_pass $backend_upstream;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header Host $host;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header X-Real-IP $remote_addr;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header X-Forwarded-Proto $scheme;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_http_version 1.1;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header Upgrade $http_upgrade;' >> /etc/nginx/conf.d/default.conf && \
    echo '        proxy_set_header Connection "upgrade";' >> /etc/nginx/conf.d/default.conf && \
    echo '    }' >> /etc/nginx/conf.d/default.conf && \
    echo '}' >> /etc/nginx/conf.d/default.conf

EXPOSE 80

# Health check using curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80 || exit 1

CMD ["nginx", "-g", "daemon off;"]


