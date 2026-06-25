import re
import uuid


class ChineseSemanticChunker:
    """Chunk Chinese text at paragraph/sentence boundaries with overlap."""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: dict) -> list[dict]:
        paragraphs = self._split_paragraphs(text)
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) <= self.chunk_size:
                current += para
            else:
                if current.strip():
                    chunks.append(self._make_chunk(current, metadata))
                current = para
        if current.strip():
            chunks.append(self._make_chunk(current, metadata))
        return self._apply_overlap(chunks)

    def _split_paragraphs(self, text: str) -> list[str]:
        parts = re.split(r"(\n\n|\n(?=[A-Z一-鿿]))", text)
        result = []
        buf = ""
        for p in parts:
            buf += p
            if len(buf) >= 64 or p.endswith(("\n\n", "\n")):
                result.append(buf)
                buf = ""
        if buf:
            result.append(buf)
        return [r for r in result if r.strip()]

    def _make_chunk(self, text: str, metadata: dict) -> dict:
        return {
            "chunk_id": str(uuid.uuid4()),
            "text": text.strip(),
            "metadata": {**metadata},
        }

    def _apply_overlap(self, chunks: list[dict]) -> list[dict]:
        if self.overlap <= 0 or len(chunks) <= 1:
            return chunks
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]["text"]
            cur = chunks[i]["text"]
            if len(prev) > self.overlap:
                chunks[i]["text"] = prev[-self.overlap:] + cur
        return chunks
