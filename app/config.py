"""
Configuration module for loading and validating environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration from environment variables."""
    
    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    BOT_OWNER_TELEGRAM_ID: int = int(os.getenv("BOT_OWNER_TELEGRAM_ID", "0"))
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    
    # Admin
    ADMIN_CODE: str = os.getenv("ADMIN_CODE", "ADMINSECRET123")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./coursemate.db")
    
    # Storage
    STORAGE_ROOT: Path = Path(os.getenv("STORAGE_ROOT", "./storage"))
    
    # AI Provider
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    
    # Rate Limiting
    PROF_RATE_LIMIT_PER_DAY: int = int(os.getenv("PROF_RATE_LIMIT_PER_DAY", "50"))
    
    # Quiz Settings
    QUIZ_QUESTIONS_DEFAULT: int = int(os.getenv("QUIZ_QUESTIONS_DEFAULT", "5"))
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN is required")
        if not cls.OPENAI_API_KEY:
            print("Warning: OPENAI_API_KEY not set. Quiz generation will fail.")
        return True


config = Config()
