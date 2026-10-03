import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Orbius"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    db_path: Path = Path(__file__).resolve().parent.parent / "orbius.db"
    demo_dir: Path = Path(__file__).resolve().parent.parent / "demo_data"
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    primary_model: str = "gemini-2.0-flash"
    fallback_model: str = "gemini-2.0-flash-lite"
    last_resort_model: str = "gemini-1.5-flash"
    max_ops_per_document: int = 6
    ops_confidence_threshold: float = 0.55


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.demo_dir.mkdir(parents=True, exist_ok=True)
