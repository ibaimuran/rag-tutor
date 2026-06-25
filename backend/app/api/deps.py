from ..models.base import SessionLocal
from ..rag.vector_store import VectorStore
from ..rag.embedder import Embedder
from ..rag.retriever import Retriever
from ..config import settings

_vector_store = None
_embedder = None
_retriever = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever(get_vector_store(), get_embedder())
    return _retriever


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(settings.chroma_persist_path)
    return _vector_store


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder(
            model_name=settings.embedding_model,
            device=settings.embedding_device,
            hf_endpoint=settings.hf_endpoint,
            local_files_only=settings.hf_local_files_only,
        )
    return _embedder
