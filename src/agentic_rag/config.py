import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR: Path = Path(__file__).resolve().parents[2]

load_dotenv(ROOT_DIR / ".env")

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DATABASE_URL_ADMIN: str = os.getenv("DATABASE_URL_ADMIN", "")
DATABASE_URL_AGENT: str = os.getenv("DATABASE_URL_AGENT", "")
DATA_DIR: Path = ROOT_DIR / "data"
EMBEDDING_DIM: int = 768
