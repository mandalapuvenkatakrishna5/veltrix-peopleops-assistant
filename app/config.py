import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

CORPUS_DIR = os.getenv(
    "CORPUS_DIR", str(PROJECT_ROOT / "data" / "corpus")
)
MANIFEST_PATH = os.getenv(
    "MANIFEST_PATH", str(PROJECT_ROOT / "data" / "manifest.json")
)
DB_PATH = os.getenv(
    "DB_PATH", str(PROJECT_ROOT / "data" / "veltrix.db")
)

APP_TODAY = os.getenv("APP_TODAY") or date.today().isoformat()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL", "http://localhost:11434/v1"
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "text-embedding-3-small"
)