"""
Document ingestion: parsing (.txt / .docx) and chunking.
Splits text into ~1500-2000 word chunks on paragraph/speaker boundaries.
"""

from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_file(file_path: str) -> str:
    """
    Parse a .txt or .docx file and return plain text.
    Raises ValueError for unsupported file types.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8")

    if suffix == ".docx":
        doc = DocxDocument(str(path))
        return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())

    raise ValueError(f"Unsupported file type: {suffix}. Only .txt and .docx are supported.")


def parse_uploaded_file(uploaded_file) -> str:
    """
    Parse a Django UploadedFile object.
    Saves to a temp path, parses, then returns text.
    """
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in (".txt", ".docx"):
        raise ValueError(f"Unsupported file type: {suffix}")

    # Read content directly from the uploaded file
    if suffix == ".txt":
        raw = uploaded_file.read()
        # Try utf-8, fall back to latin-1
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")

    # .docx — save to temp, parse, clean up
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        return parse_file(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

@dataclass
class TextChunk:
    index: int
    text: str
    word_count: int


def chunk_text(text: str, target_words: int = 1800, max_words: int = 2200) -> list[TextChunk]:
    """
    Split text into chunks of ~target_words, breaking on paragraph boundaries.

    Strategy:
    1. Split into paragraphs (double-newline separated)
    2. Accumulate paragraphs until we hit target_words
    3. If a single paragraph exceeds max_words, hard-split it on sentence boundaries
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for para in paragraphs:
        para_words = len(para.split())

        # If adding this paragraph would exceed max_words and we have content,
        # flush the current chunk
        if current and current_words + para_words > max_words:
            chunks.append("\n\n".join(current))
            current = []
            current_words = 0

        # If the paragraph itself is too long, split it on sentences
        if para_words > max_words:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_words = 0
            for sub in _split_long_paragraph(para, target_words):
                chunks.append(sub)
            continue

        current.append(para)
        current_words += para_words

        # Flush if we've hit the target
        if current_words >= target_words:
            chunks.append("\n\n".join(current))
            current = []
            current_words = 0

    # Don't forget the last chunk
    if current:
        chunks.append("\n\n".join(current))

    return [
        TextChunk(index=i, text=c, word_count=len(c.split()))
        for i, c in enumerate(chunks)
    ]


def _split_long_paragraph(paragraph: str, target_words: int) -> list[str]:
    """Split a very long paragraph on sentence boundaries."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', paragraph)

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if current and current_words + sent_words > target_words:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sent)
        current_words += sent_words

    if current:
        chunks.append(" ".join(current))

    return chunks