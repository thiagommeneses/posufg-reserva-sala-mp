"""Access to the corpus manifest (``data/normas/fontes.json``).

Single source of truth for which documents make up the corpus. Both the download
command and the ingestion pipeline read from here, so the two never disagree about
what the corpus contains.
"""

import json
from pathlib import Path

from django.conf import settings

MANIFEST_PATH = Path(settings.KNOWLEDGE_DOCUMENTS_DIR) / "fontes.json"


class ManifestError(Exception):
    """Raised when the corpus manifest is missing or malformed."""


def load_sources(source_ids: list[int] | None = None) -> list[dict]:
    """Return the corpus sources, optionally filtered by id.

    Args:
        source_ids: When given, only sources with these ids are returned.

    Returns:
        list[dict]: Source entries, each with ``id``, ``slug``, ``instituicao``,
        ``documento``, ``categoria`` and ``url``.

    Raises:
        ManifestError: If the manifest is missing, invalid or empty.
    """
    if not MANIFEST_PATH.exists():
        raise ManifestError(f"Manifesto não encontrado: {MANIFEST_PATH}")

    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifesto inválido: {exc}") from exc

    sources = data.get("fontes", [])
    if not sources:
        raise ManifestError("Manifesto não contém nenhuma fonte.")

    if source_ids:
        sources = [s for s in sources if s["id"] in source_ids]
    return sources


def find_file(source_id: int) -> Path | None:
    """Return the downloaded file for a source, if present on disk.

    Files are matched by the numeric prefix rather than the full slug: the slug in
    the manifest and the name on disk can legitimately drift when a document is
    re-saved manually, but the id never changes.

    Args:
        source_id: Identifier of the source in the manifest.

    Returns:
        Path | None: The file, or None when the source has not been downloaded.
    """
    directory = Path(settings.KNOWLEDGE_DOCUMENTS_DIR)
    matches = sorted(p for p in directory.glob(f"{source_id:02d}-*") if p.is_file())
    return matches[0] if matches else None
