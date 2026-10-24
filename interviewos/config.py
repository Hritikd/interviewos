from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class Settings(BaseModel):
    crustdata_api_key: str = ""
    gemini_api_key: str = ""
    composio_api_key: str = ""
    data_dir: Path = Field(default_factory=lambda: ROOT / "data")
    composio_user_id: str = "hritik-interviewos"
    request_timeout_seconds: float = 40
    max_jobs: int = 8
    max_contacts: int = 5


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=True)
    return Settings(
        crustdata_api_key=os.getenv("CRUSTDATA_API_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        composio_api_key=os.getenv("COMPOSIO_API_KEY", "").strip(),
    )
