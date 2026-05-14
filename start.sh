#!/bin/bash
set -e

echo "=== VOXAORA Backend Startup ==="

# Convert Railway DATABASE_URL (postgresql://) to asyncpg format
if [[ "$DATABASE_URL" == postgresql://* ]]; then
  export DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg://}"
fi
if [[ "$DATABASE_URL" == postgres://* ]]; then
  export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql+asyncpg://}"
fi
export DATABASE_SYNC_URL="${DATABASE_URL/+asyncpg/}"
export DATABASE_SYNC_URL="${DATABASE_SYNC_URL/postgresql+asyncpg:\/\//postgresql://}"

echo "DB: $DATABASE_SYNC_URL"

# Wait for PostgreSQL
echo "Waiting for database..."
python -c "
import time, sys
for i in range(60):
    try:
        import psycopg2, os
        url = os.environ['DATABASE_SYNC_URL']
        conn = psycopg2.connect(url)
        conn.close()
        print('Database ready!')
        sys.exit(0)
    except Exception as e:
        print(f'  attempt {i+1}/60: {e}')
        time.sleep(1)
sys.exit(1)
"

# Run migrations
echo "Running Alembic migrations..."
alembic upgrade heads

# Create demo accounts
echo "Seeding demo accounts..."
python create_demo_accounts.py

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
