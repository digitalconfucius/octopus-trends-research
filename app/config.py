import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/dashboard.db")
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "google")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3-flash-preview")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
