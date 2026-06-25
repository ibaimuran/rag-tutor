from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Database
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'tutor.db'}"

    # ChromaDB
    chroma_persist_path: str = str(BASE_DIR / "data" / "chroma_db")

    # HuggingFace
    hf_endpoint: str = "https://hf-mirror.com"
    hf_local_files_only: bool = False

    # Embedding
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_device: str = "cpu"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # BKT defaults
    bkt_default_p_l0: float = 0.50
    bkt_default_p_t: float = 0.20
    bkt_default_p_g: float = 0.15
    bkt_default_p_s: float = 0.10

    # Mastery thresholds
    mastery_threshold: float = 0.80
    relearn_threshold: float = 0.60

    # RAG
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 5

    # Tutor
    diagnose_rounds: int = 1
    teach_rounds: int = 5
    mastery_check_rounds: int = 2

    # Frontend
    static_dir: str = str(BASE_DIR.parent / "frontend" / "static")
    template_dir: str = str(BASE_DIR.parent / "frontend" / "templates")

    class Config:
        env_file = str(BASE_DIR.parent / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
