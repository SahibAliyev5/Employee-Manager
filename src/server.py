from contextlib import asynccontextmanager
from fastmcp import FastMCP
from dotenv import load_dotenv

from db import init_pool, close_pool
from tools import register_tools

# Load the database DSN from .env
load_dotenv()

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manages the startup and teardown lifecycle of the FastMCP server."""
    await init_pool()
    try:
        yield {}
    finally:
        await close_pool()

# Initialize the server with the async context lifespan
mcp = FastMCP("hermes-ems", lifespan=lifespan)

# Inject the tools into the FastMCP instance
register_tools(mcp)

if __name__ == "__main__":
    # Start the server listening on stdio (FastMCP default protocol transport)
    mcp.run()