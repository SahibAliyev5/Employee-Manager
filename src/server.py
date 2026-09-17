# ems_server.py
from contextlib import asynccontextmanager
from fastmcp import FastMCP
import sys
from pathlib import Path

# Ensure the directory containing this script (src/) is in sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from db import init_pool, close_pool
from tools import register_tools

@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initializes asyncpg pool on server boot and cleans up on shutdown."""
    await init_pool()
    try:
        yield
    finally:
        await close_pool()

mcp = FastMCP("hermes-ems", lifespan=server_lifespan)

# Register all extracted tools
register_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
