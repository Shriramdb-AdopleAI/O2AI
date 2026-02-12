#!/bin/bash

# PostgreSQL Setup Script for O2AI Fax Automation
# This script automates the PostgreSQL setup process

set -e  # Exit on error

echo "=========================================="
echo "PostgreSQL Setup for O2AI Fax Automation"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_NAME=${POSTGRES_DB:-"o2ai_fax_automation"}
DB_USER=${POSTGRES_USER:-"postgres"}
DB_PASSWORD=${POSTGRES_PASSWORD:-"postgres"}
DB_HOST=${POSTGRES_HOST:-"localhost"}
DB_PORT=${POSTGRES_PORT:-"5432"}

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if PostgreSQL is installed
check_postgres() {
    if command -v psql &> /dev/null; then
        print_success "PostgreSQL client is installed"
        return 0
    else
        print_error "PostgreSQL client is not installed"
        return 1
    fi
}

# Check if PostgreSQL is running
check_postgres_running() {
    if pg_isready -h $DB_HOST -p $DB_PORT &> /dev/null; then
        print_success "PostgreSQL server is running"
        return 0
    else
        print_error "PostgreSQL server is not running"
        print_info "Try: sudo systemctl start postgresql"
        print_info "Or with Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres --name postgres postgres:15"
        return 1
    fi
}

# Create database
create_database() {
    print_info "Creating database: $DB_NAME"
    
    # Check if database exists
    if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
        print_info "Database $DB_NAME already exists"
        read -p "Do you want to drop and recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "DROP DATABASE $DB_NAME;"
            print_success "Dropped existing database"
        else
            print_info "Using existing database"
            return 0
        fi
    fi
    
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME;"
    print_success "Database created: $DB_NAME"
}

# Create schema
create_schema() {
    print_info "Creating database schema"
    
    if [ ! -f "schema.sql" ]; then
        print_error "schema.sql not found in current directory"
        return 1
    fi
    
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f schema.sql
    print_success "Schema created successfully"
}

# Install Python dependencies
install_dependencies() {
    print_info "Installing Python dependencies"
    
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found"
        return 1
    fi
    
    pip install psycopg2-binary -q
    print_success "PostgreSQL driver installed"
}

# Update environment file
update_env() {
    print_info "Updating environment configuration"
    
    DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
    
    if [ -f ".env" ]; then
        # Backup existing .env
        cp .env .env.backup
        print_success "Backed up existing .env to .env.backup"
        
        # Update or add DATABASE_URL
        if grep -q "^DATABASE_URL=" .env; then
            sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
        else
            echo "" >> .env
            echo "# PostgreSQL Configuration" >> .env
            echo "DATABASE_URL=$DATABASE_URL" >> .env
        fi
    else
        # Create new .env from template
        if [ -f ".env.postgres.example" ]; then
            cp .env.postgres.example .env
            sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
        else
            echo "DATABASE_URL=$DATABASE_URL" > .env
        fi
    fi
    
    print_success "Environment file updated"
    print_info "DATABASE_URL=$DATABASE_URL"
}

# Main setup process
main() {
    echo ""
    print_info "Starting PostgreSQL setup..."
    echo ""
    
    # Check prerequisites
    if ! check_postgres; then
        print_error "Please install PostgreSQL first"
        exit 1
    fi
    
    if ! check_postgres_running; then
        print_error "Please start PostgreSQL first"
        exit 1
    fi
    
    # Run setup steps
    create_database || exit 1
    create_schema || exit 1
    install_dependencies || exit 1
    update_env || exit 1
    
    echo ""
    echo "=========================================="
    print_success "PostgreSQL setup completed!"
    echo "=========================================="
    echo ""
    print_info "Next steps:"
    echo "  1. Run migration: python migrate_to_postgres.py"
    echo "  2. Test your application: python main.py"
    echo ""
    print_info "Database connection:"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    echo ""
}

# Run main function
main
