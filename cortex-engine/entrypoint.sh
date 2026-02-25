#!/bin/sh
set -e

echo "==> Enabling pgvector extension..."
python -c "
import os, sqlalchemy
url = os.environ.get('DATABASE_URL', 'postgresql://postgres@localhost:5432/cortex')
# Railway uses postgres:// but SQLAlchemy needs postgresql://
url = url.replace('postgres://', 'postgresql://', 1)
engine = sqlalchemy.create_engine(url)
with engine.connect() as conn:
    conn.execute(sqlalchemy.text('CREATE EXTENSION IF NOT EXISTS vector'))
    conn.commit()
print('pgvector extension ready.')
"

echo "==> Running alembic migrations..."
alembic upgrade head

echo "==> Starting uvicorn..."
exec uvicorn cortex.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
