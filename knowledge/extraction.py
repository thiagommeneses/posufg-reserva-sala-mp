"""Text extraction from the corpus files.

Handles the three formats accepted by the corpus: PDF (via pypdf), HTML (via
trafilatura, which strips menus, footers and other boilerplate) and plain text.

Extraction is where silent corruption tends to surface. A scanned PDF without a text
layer, a captcha page saved as HTML, or a JavaScript shell all read as valid files but
yield little or no text. :func:`extract` refuses those instead of letting them into the
index, where they would consume space and never match a query.
"""

import html as html_lib
import re
from dataclasses import dataclass
from pathlib import Path

import trafilatura
from pypdf import PdfReader
from pypdf.errors import PdfReadError

#: Below this word count a file is almost certainly an image-only PDF, a captcha page
#: or a JavaScript shell rather than a real document.
MIN_WORDS = 150

SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".txt"}


class ExtractionError(Exception):
    """Raised when a file cannot be turned into usable text."""


@dataclass(frozen=True)
class ExtractedText:
    """Result of extracting text from a single file."""

    text: str
    word_count: int
    page_count: int | None


def extract(path: Path) -> ExtractedText:
    """Extract usable text from a corpus file.

    Args:
        path: File to extract, in PDF, HTML or plain text.

    Returns:
        ExtractedText: The normalised text with its word and page counts.

    Raises:
        ExtractionError: If the format is unsupported, the file cannot be read, or
            the extracted text is too short to be a real document.
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractionError(f"Formato não suportado: {suffix}")

    if suffix == ".pdf":
        text, page_count = _extract_pdf(path)
    elif suffix in (".html", ".htm"):
        text, page_count = _extract_html(path), None
    else:
        text, page_count = path.read_text(encoding="utf-8", errors="ignore"), None

    text = normalise(text)
    word_count = len(text.split())

    if word_count < MIN_WORDS:
        causa = (
            "PDF digitalizado, sem camada de texto"
            if suffix == ".pdf"
            else "página de captcha ou casca renderizada por JavaScript"
        )
        raise ExtractionError(
            f"Apenas {word_count} palavras extraídas (mínimo {MIN_WORDS}). Causa provável: {causa}."
        )

    return ExtractedText(text=text, word_count=word_count, page_count=page_count)


def normalise(text: str) -> str:
    """Collapse whitespace while preserving paragraph breaks.

    Paragraph breaks matter because the chunker uses them as split points.

    Args:
        text: Raw extracted text.

    Returns:
        str: Text with runs of spaces collapsed and blank lines normalised.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _extract_pdf(path: Path) -> tuple[str, int]:
    """Extract text and page count from a PDF.

    Raises:
        ExtractionError: If the file cannot be parsed as a PDF.
    """
    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, ValueError) as exc:
        raise ExtractionError(f"Falha ao ler o PDF: {exc}") from exc
    return "\n\n".join(pages), len(pages)


#: Blocos que nunca contêm o texto da norma.
BOILERPLATE_TAGS = ("script", "style", "nav", "footer", "header", "form", "aside")


def _extract_html(path: Path) -> str:
    """Extract the main content of an HTML page, discarding boilerplate.

    trafilatura is tried first because it produces the cleanest text. Institutional
    portals, however, often lay content out in tables and nested lists that its
    boilerplate detector mistakes for navigation — on three pages of this corpus it
    returned under 70 words where the page held several hundred. When that happens we
    fall back to plain tag stripping: noisier text, but the rules survive.

    Args:
        path: HTML file to extract.

    Returns:
        str: The extracted text, from whichever strategy recovered more content.
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")

    main_content = (
        trafilatura.extract(
            raw,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        or ""
    )
    if len(main_content.split()) >= MIN_WORDS:
        return main_content

    stripped = _strip_tags(raw)
    return stripped if len(stripped.split()) > len(main_content.split()) else main_content


def _strip_tags(raw: str) -> str:
    """Return the visible text of an HTML document, minus navigation blocks."""
    for tag in BOILERPLATE_TAGS:
        raw = re.sub(rf"(?is)<{tag}[^>]*>.*?</{tag}>", " ", raw)
    return html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
