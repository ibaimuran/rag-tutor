from .vector_store import VectorStore
from .embedder import Embedder


class Retriever:
    def __init__(self, vector_store: VectorStore, embedder: Embedder):
        self.vs = vector_store
        self.embedder = embedder

    def retrieve_for_concept(self, course_id: int, title: str, description: str = "", top_k: int = 5) -> list[dict]:
        collection = self.vs.get_or_create_collection(course_id)
        query = f"{title} {description}".strip()
        query_embedding = self.embedder.embed_query(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        return self._format_results(results)

    def retrieve_for_chat(self, course_id: int, query: str, top_k: int = 3) -> list[dict]:
        collection = self.vs.get_or_create_collection(course_id)
        query_embedding = self.embedder.embed_query(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        return self._format_results(results)

    def _format_results(self, results) -> list[dict]:
        if not results or not results.get("documents") or not results["documents"][0]:
            return []
        docs = results["documents"][0]
        metas = results.get("metadatas", [[]])[0]
        return [
            {"text": doc, "metadata": meta or {}}
            for doc, meta in zip(docs, metas)
        ]
