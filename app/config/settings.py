import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    # Project Paths
    APP_DIR: Path = Path(__file__).resolve().parent.parent
    PROJECT_ROOT: Path = APP_DIR.parent
    
    # Storage Paths
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DB_PATH: Path = DATA_DIR / "database" / "newsletter.db"
    RAW_ARTICLES_DIR: Path = DATA_DIR / "raw_articles"
    NEWSLETTERS_DIR: Path = DATA_DIR / "newsletters"
    EMBEDDINGS_DIR: Path = DATA_DIR / "embeddings"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"

    # Gemini API Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

    # Ollama Local Settings (Optional Fallback)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # Embedding Settings
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # SMTP / Email Settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_TO_EMAIL: str = os.getenv("SMTP_TO_EMAIL", "")

    # Slack Integration Settings
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # Application Settings
    ENV: str = os.getenv("ENV", "development")
    
    def __init__(self):
        # Ensure all required directories exist
        self.RAW_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
        self.NEWSLETTERS_DIR.mkdir(parents=True, exist_ok=True)
        self.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self) -> bool:
        """Validates critical settings."""
        if not self.GEMINI_API_KEY:
            # We don't fail immediately to allow offline / dry-run dry-tests
            return False
        return True

settings = Settings()
