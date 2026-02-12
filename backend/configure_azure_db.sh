#!/bin/bash
# Azure PostgreSQL Configuration Script
# This script helps you configure your .env file for Azure PostgreSQL

echo "=========================================="
echo "Azure PostgreSQL Configuration"
echo "=========================================="
echo ""
echo "Your Azure PostgreSQL Server:"
echo "Host: o2aifaxautomationdatabaseserver.postgres.database.azure.com"
echo ""
echo "Please provide the following information:"
echo ""

# Read database name
read -p "Database Name [o2ai_fax_automation]: " DB_NAME
DB_NAME=${DB_NAME:-o2ai_fax_automation}

# Read username
read -p "Database Username: " DB_USER
if [ -z "$DB_USER" ]; then
    echo "Error: Username is required!"
    exit 1
fi

# Read password (hidden)
read -sp "Database Password: " DB_PASSWORD
echo ""
if [ -z "$DB_PASSWORD" ]; then
    echo "Error: Password is required!"
    exit 1
fi

# Read port
read -p "Port [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}

# Create/update .env file
ENV_FILE=".env"

# Check if .env exists, if not create it
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# Remove old database settings if they exist
sed -i '/^DB_HOST=/d' "$ENV_FILE"
sed -i '/^DB_PORT=/d' "$ENV_FILE"
sed -i '/^DB_NAME=/d' "$ENV_FILE"
sed -i '/^DB_USER=/d' "$ENV_FILE"
sed -i '/^DB_PASSWORD=/d' "$ENV_FILE"
sed -i '/^DB_SSL_MODE=/d' "$ENV_FILE"
sed -i '/^DATABASE_URL=/d' "$ENV_FILE"
sed -i '/^POSTGRES_HOST=/d' "$ENV_FILE"
sed -i '/^POSTGRES_PORT=/d' "$ENV_FILE"
sed -i '/^POSTGRES_DB=/d' "$ENV_FILE"
sed -i '/^POSTGRES_USER=/d' "$ENV_FILE"
sed -i '/^POSTGRES_PASSWORD=/d' "$ENV_FILE"

# Add new database settings
echo "" >> "$ENV_FILE"
echo "# Azure PostgreSQL Configuration" >> "$ENV_FILE"
echo "DB_HOST=o2aifaxautomationdatabaseserver.postgres.database.azure.com" >> "$ENV_FILE"
echo "DB_PORT=$DB_PORT" >> "$ENV_FILE"
echo "DB_NAME=$DB_NAME" >> "$ENV_FILE"
echo "DB_USER=$DB_USER" >> "$ENV_FILE"
echo "DB_PASSWORD=$DB_PASSWORD" >> "$ENV_FILE"
echo "DB_SSL_MODE=require" >> "$ENV_FILE"

echo ""
echo "=========================================="
echo "✅ Configuration saved to .env file!"
echo "=========================================="
echo ""
echo "Database Configuration:"
echo "  Host: o2aifaxautomationdatabaseserver.postgres.database.azure.com"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  Username: $DB_USER"
echo "  SSL Mode: require"
echo ""
echo "You can now start your application!"
