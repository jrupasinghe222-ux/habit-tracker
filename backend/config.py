"""Environment configuration. Never return secrets in API responses."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


@lru_cache
def supabase_url() -> str:
    value = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not value.startswith("https://") or not value.endswith(".supabase.co"):
        raise ValueError("Set SUPABASE_URL to the project's HTTPS supabase.co URL.")
    return value
