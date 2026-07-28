"""Segmentation of normative text into retrievable chunks.

The separator order is tuned for Brazilian legal drafting rather than prose. Splitting
on ``Art.`` and ``§`` first keeps a rule intact inside a single chunk, which matters at
retrieval time: a chunk that ends halfway through an article answers nothing, and a
chunk that merges two unrelated articles dilutes the embedding.
"""

from django.conf import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter

#: Tried in order. The first separators follow the structure of a Brazilian norm;
#: the later ones are the usual prose fallbacks.
SEPARATORS = [
    "\nArt. ",
    "\nArtigo ",
    "\nCAPÍTULO ",
    "\nSeção ",
    "\n§",
    "\nParágrafo ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]


def split(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: Normalised document text.
        chunk_size: Maximum chunk length in characters. Defaults to ``CHUNK_SIZE``.
        overlap: Overlap between consecutive chunks. Defaults to ``CHUNK_OVERLAP``.

    Returns:
        list[str]: Non-empty chunks, in reading order.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.CHUNK_SIZE,
        chunk_overlap=overlap if overlap is not None else settings.CHUNK_OVERLAP,
        separators=SEPARATORS,
        keep_separator=True,
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
