import os
from pathlib import Path


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5", device: str = "cpu",
                 hf_endpoint: str = "", local_files_only: bool = False):
        self.model_name = model_name
        self._model = None
        self._device = device
        self._hf_endpoint = hf_endpoint
        self._local_files_only = local_files_only

    @property
    def model(self):
        if self._model is None:
            if self._hf_endpoint:
                os.environ.setdefault("HF_ENDPOINT", self._hf_endpoint)

            from sentence_transformers import SentenceTransformer

            model_path = self.model_name
            if Path(self.model_name).is_dir():
                # Local path: load directly without touching HF Hub
                model_path = str(Path(self.model_name).resolve())

            self._model = SentenceTransformer(
                model_path,
                device=self._device,
                local_files_only=self._local_files_only or Path(self.model_name).is_dir(),
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, query: str) -> list[float]:
        return self.model.encode(
            f"为这个句子生成表示以用于检索相关文章：{query}",
            normalize_embeddings=True,
        ).tolist()
