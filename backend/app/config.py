"""
Central configuration for OmniRAG backend.
All values are loaded from environment variables (.env) so nothing is hardcoded.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_VISION_MODEL: str = "llava:7b"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Vector store
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # Storage
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 100

    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"

    # OCR
    TESSERACT_CMD: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

# Ensure runtime directories exist
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
