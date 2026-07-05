"""Writing verses out of the app: clipboard-adjacent, but to files.

Four formats, chosen so each has an obvious consumer: plain text to paste
into a document, Markdown to drop into notes, JSON for scripts, and CSV for
a spreadsheet. Every writer takes the same list of verses, so search results
and a passage export share one code path.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
from pathlib import Path

from ..models.verse import Verse

TEXT = "txt"
MARKDOWN = "md"
JSON = "json"
CSV = "csv"

#: Offered in the export dialog, in this order.
FORMATS: tuple[tuple[str, str], ...] = (
    (TEXT, "Plain text"),
    (MARKDOWN, "Markdown"),
    (JSON, "JSON"),
    (CSV, "CSV"),
)

DEFAULT_EXPORT_DIR = Path.home() / "Documents"


class ExportError(RuntimeError):
    """Raised when the file could not be written."""


def render(verses: list[Verse], fmt: str, translation_code: str, title: str = "") -> str:
    """Serialise verses in `fmt`. Unknown formats fall back to plain text."""
    writers = {TEXT: _as_text, MARKDOWN: _as_markdown, JSON: _as_json, CSV: _as_csv}
    return writers.get(fmt, _as_text)(verses, translation_code, title)


def export(
    verses: list[Verse],
    fmt: str,
    translation_code: str,
    path: Path,
    title: str = "",
) -> Path:
    """Write verses to `path`, creating the directory if needed."""
    if not verses:
        raise ExportError("nothing to export")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(verses, fmt, translation_code, title), encoding="utf-8")
    except OSError as error:
        raise ExportError(str(error)) from error
    return path


def default_path(fmt: str, slug: str, directory: Path | None = None) -> Path:
    """A dated, collision-resistant filename so repeated exports don't
    silently overwrite each other."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug).strip("-").lower()
    safe = safe or "bible"
    return (directory or DEFAULT_EXPORT_DIR) / f"{safe}-{stamp}.{fmt}"


# ----------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------


def _as_text(verses: list[Verse], translation_code: str, title: str) -> str:
    lines = []
    if title:
        lines += [title, "=" * len(title), ""]
    lines += [f"{v.reference} ({translation_code})\n{v.text}\n" for v in verses]
    return "\n".join(lines).rstrip() + "\n"


def _as_markdown(verses: list[Verse], translation_code: str, title: str) -> str:
    lines = [f"# {title}" if title else f"# {translation_code} passages", ""]
    for verse in verses:
        lines.append(f"> {verse.text}")
        lines.append(">")
        lines.append(f"> - **{verse.reference}** ({translation_code})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _as_json(verses: list[Verse], translation_code: str, title: str) -> str:
    payload = {
        "title": title or None,
        "translation": translation_code,
        "count": len(verses),
        "verses": [
            {
                "reference": v.reference,
                "book": v.book_name,
                "book_id": v.book_id,
                "chapter": v.chapter,
                "verse": v.verse,
                "text": v.text,
            }
            for v in verses
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _as_csv(verses: list[Verse], translation_code: str, title: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["reference", "book", "chapter", "verse", "translation", "text"])
    for v in verses:
        writer.writerow([v.reference, v.book_name, v.chapter, v.verse, translation_code, v.text])
    return buffer.getvalue()
