import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseModel):
    app_name: str = "Orbius"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    db_path: Path = Path(__file__).resolve().parent.parent / "orbius.db"
    demo_dir: Path = Path(__file__).resolve().parent.parent / "demo_data"
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    brevo_api_key: Optional[str] = os.getenv("BREVO_API_KEY")
    jira_api_token: Optional[str] = os.getenv("JIRA_API_TOKEN")
    jira_email: Optional[str] = os.getenv("JIRA_EMAIL")
    jira_domain: Optional[str] = os.getenv("JIRA_DOMAIN")
    jwt_secret: str = os.getenv("JWT_SECRET", "orbius_secret_key_2026_enterprise_saas")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
    primary_model: str = "gemini-3.8-flash"
    fallback_model: str = "gemini-3.7-flash"
    last_resort_model: str = "gemini-3.1-flash-lite"
    max_ops_per_document: int = 6
    ops_confidence_threshold: float = 0.55


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.demo_dir.mkdir(parents=True, exist_ok=True)

