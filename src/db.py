# db.py
import os
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

_pool: asyncpg.Pool | None = None

# Load .env variables into this process
load_dotenv()

async def init_pool():
    global _pool
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        raise ValueError("DB_DSN environment variable is not set.")
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

@asynccontextmanager
async def get_connection():
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    async with _pool.acquire() as conn:
        yield conn