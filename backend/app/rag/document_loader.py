from pathlib import Path


class DocumentLoader:
    def load_directory(self, path: Path) -> list[dict]:
        documents = []
        for filepath in path.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix in (".md", ".txt"):
                text = filepath.read_text(encoding="utf-8")
            elif filepath.suffix == ".pdf":
                text = self._extract_pdf(filepath)
            else:
                continue
            if not text.strip():
                continue
            documents.append({
                "filename": filepath.name,
                "text": text,
                "metadata": {
                    "source": str(filepath),
                    "chapter": filepath.parent.name,
                }
            })
        return documents

    def _extract_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise ImportError("pypdf is required to load PDF files.")
