import os
import asyncpg
from contextlib import asynccontextmanager

# Global connection pool reference
_pool: asyncpg.Pool | None = None

async def init_pool():
    """Initializes the asyncpg connection pool."""
    global _pool
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        raise ValueError("DB_DSN environment variable is not set.")
    
    # Establish connection pool targeting 10.218.248.21
    _pool = await asyncpg.create_pool(dsn)

async def close_pool():
    """Closes the asyncpg connection pool gracefully."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

@asynccontextmanager
async def get_connection():
    """Context manager for safely acquiring and releasing database connections."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    
    async with _pool.acquire() as conn:
        yield conn