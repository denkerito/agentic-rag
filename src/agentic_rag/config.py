import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR: Path = Path(__file__).resolve().parents[2]

load_dotenv(ROOT_DIR / ".env")

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DATA_DIR: Path = ROOT_DIR / "data"
