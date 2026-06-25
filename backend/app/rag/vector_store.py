import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    def __init__(self, persist_path: str):
        self.client = chromadb.PersistentClient(
            path=persist_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def get_or_create_collection(self, course_id: int):
        return self.client.get_or_create_collection(
            name=f"course_{course_id}",
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, course_id: int, chunks: list[dict], embeddings: list[list[float]]):
        if not chunks:
            return
        collection = self.get_or_create_collection(course_id)
        collection.add(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )

    def delete_collection(self, course_id: int):
        try:
            self.client.delete_collection(f"course_{course_id}")
        except Exception:
            pass
