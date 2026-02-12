# PostgreSQL Migration Guide

This guide will help you migrate from SQLite to PostgreSQL for the O2AI Fax Automation application.

## Prerequisites

1. **PostgreSQL Installation**
   - Install PostgreSQL 12 or higher
   - Ensure PostgreSQL service is running

### Installation Commands

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (using Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:**
- Download and install from: https://www.postgresql.org/download/windows/
- Or use Docker: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres --name postgres postgres:15`

**Docker (Recommended for development):**
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=o2ai_fax_automation \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15
```

## Migration Steps

### Step 1: Create PostgreSQL Database

```bash
# Connect to PostgreSQL as superuser
sudo -u postgres psql

# Or if using Docker:
docker exec -it postgres psql -U postgres

# Create database
CREATE DATABASE o2ai_fax_automation;

# Create user (optional, if you want a dedicated user)
CREATE USER o2ai_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE o2ai_fax_automation TO o2ai_user;

# Exit psql
\q
```

### Step 2: Install Python Dependencies

```bash
cd backend
pip install psycopg2-binary
# Or install all requirements
pip install -r requirements.txt
```

### Step 3: Create Database Schema

```bash
# Using psql
psql -U postgres -d o2ai_fax_automation -f schema.sql

# Or using Docker:
docker exec -i postgres psql -U postgres -d o2ai_fax_automation < schema.sql
```

### Step 4: Configure Environment Variables

Create or update your `.env` file in the `backend` directory:

```bash
# PostgreSQL Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/o2ai_fax_automation

# Or with custom user:
# DATABASE_URL=postgresql://o2ai_user:your_secure_password@localhost:5432/o2ai_fax_automation

# For remote PostgreSQL:
# DATABASE_URL=postgresql://user:password@hostname:5432/database_name
```

### Step 5: Backup SQLite Database

```bash
cd backend
cp data/users.db data/users.db.backup
```

### Step 6: Run Migration Script

```bash
cd backend

# Set environment variables (if not in .env)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=o2ai_fax_automation
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

# Run migration
python migrate_to_postgres.py
```

### Step 7: Verify Migration

The migration script will automatically verify the data. You should see output like:

```
✓ users: SQLite=5, PostgreSQL=5
✓ user_sessions: SQLite=7, PostgreSQL=7
✓ analysis_cache: SQLite=6, PostgreSQL=6
✓ ground_truth: SQLite=372, PostgreSQL=372
```

### Step 8: Test Your Application

```bash
# Start the backend
cd backend
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

Test the following:
- Login functionality
- File upload and processing
- View processed files
- Analysis cache functionality

## Troubleshooting

### Connection Issues

**Error: `could not connect to server`**
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Check if PostgreSQL is listening on the correct port: `sudo netstat -plnt | grep 5432`

**Error: `password authentication failed`**
- Verify your credentials in the DATABASE_URL
- Check PostgreSQL authentication settings in `pg_hba.conf`

### Migration Issues

**Error: `database does not exist`**
- Create the database first (see Step 1)

**Error: `relation already exists`**
- Drop existing tables: `psql -U postgres -d o2ai_fax_automation -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`
- Then re-run the schema creation (Step 3)

### Performance Issues

If you experience slow queries:

```sql
-- Create additional indexes
CREATE INDEX idx_ground_truth_created_at ON ground_truth(created_at);
CREATE INDEX idx_analysis_cache_created_at ON analysis_cache(created_at);

-- Analyze tables for query optimization
ANALYZE users;
ANALYZE user_sessions;
ANALYZE analysis_cache;
ANALYZE ground_truth;
```

## Database Management

### Backup PostgreSQL Database

```bash
# Backup to file
pg_dump -U postgres o2ai_fax_automation > backup_$(date +%Y%m%d_%H%M%S).sql

# Or with Docker:
docker exec postgres pg_dump -U postgres o2ai_fax_automation > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore PostgreSQL Database

```bash
# Restore from file
psql -U postgres o2ai_fax_automation < backup_20231205_120000.sql

# Or with Docker:
docker exec -i postgres psql -U postgres o2ai_fax_automation < backup_20231205_120000.sql
```

### Monitor Database Size

```sql
-- Connect to database
psql -U postgres -d o2ai_fax_automation

-- Check database size
SELECT pg_size_pretty(pg_database_size('o2ai_fax_automation'));

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Vacuum and Analyze

Regular maintenance for optimal performance:

```sql
-- Vacuum all tables
VACUUM ANALYZE;

-- Or for specific table
VACUUM ANALYZE ground_truth;
```

## Production Deployment

### Security Best Practices

1. **Use strong passwords**
   ```sql
   ALTER USER postgres WITH PASSWORD 'very_strong_random_password';
   ```

2. **Restrict network access**
   - Edit `postgresql.conf`: `listen_addresses = 'localhost'`
   - Edit `pg_hba.conf` to restrict connections

3. **Use SSL/TLS**
   ```bash
   DATABASE_URL=postgresql://user:password@hostname:5432/database?sslmode=require
   ```

4. **Regular backups**
   - Set up automated backups using cron or systemd timers
   - Store backups in a secure, off-site location

### Connection Pooling

For production, consider using connection pooling with PgBouncer:

```bash
# Install PgBouncer
sudo apt install pgbouncer

# Configure and use
DATABASE_URL=postgresql://user:password@localhost:6432/database
```

## Rollback Plan

If you need to rollback to SQLite:

1. Stop the application
2. Restore the SQLite backup:
   ```bash
   cp data/users.db.backup data/users.db
   ```
3. Update `backend/models/database.py`:
   ```python
   DATABASE_URL = "sqlite:///./data/users.db"
   engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
   ```
4. Restart the application

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy PostgreSQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)

## Support

If you encounter issues during migration, please check:
1. PostgreSQL logs: `/var/log/postgresql/` or `docker logs postgres`
2. Application logs: `ocr_processing.log`
3. Migration script output for specific error messages
