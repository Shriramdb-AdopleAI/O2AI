# Quick Start: PostgreSQL Migration

This guide provides the fastest way to migrate from SQLite to PostgreSQL.

## Option 1: Using Docker (Recommended for Quick Setup)

### 1. Start PostgreSQL with Docker Compose

```bash
cd backend
docker-compose -f docker-compose.postgres.yml up -d
```

This will:
- Start PostgreSQL on port 5432
- Start pgAdmin on port 5050 (optional web UI)
- Automatically create the database schema

### 2. Install Python Dependencies

```bash
pip install psycopg2-binary
```

### 3. Run Migration

```bash
python migrate_to_postgres.py
```

### 4. Update Your Application

The application will automatically use PostgreSQL if `DATABASE_URL` is set in your environment.

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/o2ai_fax_automation
python main.py
```

**Done!** Your application is now using PostgreSQL.

---

## Option 2: Using Existing PostgreSQL Installation

### 1. Run Setup Script

```bash
cd backend
./setup_postgres.sh
```

This automated script will:
- Check PostgreSQL installation
- Create the database
- Create the schema
- Install dependencies
- Update environment configuration

### 2. Run Migration

```bash
python migrate_to_postgres.py
```

### 3. Start Your Application

```bash
python main.py
```

---

## Option 3: Manual Setup

### 1. Create Database

```bash
psql -U postgres -c "CREATE DATABASE o2ai_fax_automation;"
```

### 2. Create Schema

```bash
psql -U postgres -d o2ai_fax_automation -f schema.sql
```

### 3. Install Dependencies

```bash
pip install psycopg2-binary
```

### 4. Set Environment Variable

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/o2ai_fax_automation
```

### 5. Run Migration

```bash
python migrate_to_postgres.py
```

### 6. Start Application

```bash
python main.py
```

---

## Verification

After migration, verify your data:

```bash
# Connect to PostgreSQL
psql -U postgres -d o2ai_fax_automation

# Check table counts
SELECT 'users' as table_name, COUNT(*) FROM users
UNION ALL
SELECT 'user_sessions', COUNT(*) FROM user_sessions
UNION ALL
SELECT 'analysis_cache', COUNT(*) FROM analysis_cache
UNION ALL
SELECT 'ground_truth', COUNT(*) FROM ground_truth;
```

Expected output (based on your current data):
```
 table_name     | count
----------------+-------
 users          |     5
 user_sessions  |     7
 analysis_cache |     6
 ground_truth   |   372
```

---

## Accessing pgAdmin (Docker only)

If you used Docker Compose, you can access pgAdmin at:
- URL: http://localhost:5050
- Email: admin@o2ai.com
- Password: admin

To connect to your database in pgAdmin:
1. Right-click "Servers" → "Register" → "Server"
2. General tab: Name = "O2AI Database"
3. Connection tab:
   - Host: postgres (or localhost if accessing from host machine)
   - Port: 5432
   - Database: o2ai_fax_automation
   - Username: postgres
   - Password: postgres

---

## Troubleshooting

### PostgreSQL not running?

**Docker:**
```bash
docker-compose -f docker-compose.postgres.yml up -d
```

**System service:**
```bash
sudo systemctl start postgresql
```

### Connection refused?

Check if PostgreSQL is listening:
```bash
sudo netstat -plnt | grep 5432
```

### Migration failed?

1. Check PostgreSQL logs:
   ```bash
   # Docker
   docker logs o2ai_postgres
   
   # System
   sudo tail -f /var/log/postgresql/postgresql-*.log
   ```

2. Verify database exists:
   ```bash
   psql -U postgres -l | grep o2ai
   ```

3. Check schema:
   ```bash
   psql -U postgres -d o2ai_fax_automation -c "\dt"
   ```

---

## Next Steps

1. **Test your application thoroughly**
   - Login/logout
   - File upload
   - Data retrieval
   - Analysis cache

2. **Backup your SQLite database** (after successful migration)
   ```bash
   mv data/users.db data/users.db.backup
   ```

3. **Set up regular PostgreSQL backups**
   ```bash
   # Add to crontab
   0 2 * * * pg_dump -U postgres o2ai_fax_automation > /backups/o2ai_$(date +\%Y\%m\%d).sql
   ```

4. **Monitor performance**
   - Check query performance
   - Monitor database size
   - Set up connection pooling if needed

---

## Rollback (if needed)

If you encounter issues and need to rollback to SQLite:

1. Stop the application
2. Restore SQLite database:
   ```bash
   cp data/users.db.backup data/users.db
   ```
3. Update `models/database.py`:
   ```python
   DATABASE_URL = "sqlite:///./data/users.db"
   ```
4. Restart application

---

For detailed information, see [POSTGRES_MIGRATION.md](../POSTGRES_MIGRATION.md)
