import os
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# Database
DB_DSN = os.environ.get("DB_DSN", "postgresql://postgres:Abc123!@localhost:5432/employee_management")

# LLM Inference (Hermes)
HERMES_BASE_URL = os.environ.get("HERMES_BASE_URL", "http://localhost:11434/v1")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "ollama")
MODEL_NAME = os.environ.get("HERMES_MODEL", "hf.co/gabriellarson/Hermes-4-14B-GGUF:Q4_K_M")


# Resolve relative to the src/ directory where config.py lives
SRC_DIR = Path(__file__).parent.resolve()
SERVER_SCRIPT = os.environ.get("FAST_MCP_SERVER_SCRIPT", "server.py")

# If it's a relative path, resolve it relative to src/
SERVER_PATH = (SRC_DIR / SERVER_SCRIPT).resolve() if not Path(SERVER_SCRIPT).is_absolute() else Path(SERVER_SCRIPT)

llm_client = AsyncOpenAI(
    base_url=HERMES_BASE_URL,
    api_key=HERMES_API_KEY
)