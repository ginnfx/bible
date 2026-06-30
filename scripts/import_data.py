#!/usr/bin/env python3
"""One-time data import pipeline for bible-tui.

Pulls public-domain translations, Strong's tagging, cross-references, and
commentary from their upstream sources, normalizes book naming to the
canonical 66-book list, and writes directly into bible.db's schema. This is
throwaway tooling - it is not imported by the shipped app (aside from the
`bible import-data` convenience hook for rebuilding from a repo
checkout) and is safe to re-run: `run_import` recreates the db from scratch.

Usage:
    python scripts/import_data.py [--cache-dir DIR] [--db-path PATH]

Sources (all public domain text; the Strong's lexicon JSON and the
cross-reference dataset are CC-BY-SA compilations over public-domain source
material - see README for attribution):
  - scrollmapper/bible_databases (KJV, ASV sqlite exports; KJVA OSIS JSON for
    Strong's-tagged text)
  - seven1m/open-bibles (WEB, USFX XML)
  - openscriptures/strongs (Hebrew + Greek Strong's dictionaries)
  - scrollmapper/bible_databases sources/extras (openbible.info cross-references)
  - lyteword/mhenry-concise (Matthew Henry's Concise Commentary, public domain)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bible_tui.data.database import connect, init_schema  # noqa: E402
from bible_tui.models.book import CANONICAL_BOOKS  # noqa: E402

RAW_BASE = "https://raw.githubusercontent.com"

SOURCES = {
    "KJV.db": f"{RAW_BASE}/scrollmapper/bible_databases/master/formats/sqlite/KJV.db",
    "ASV.db": f"{RAW_BASE}/scrollmapper/bible_databases/master/formats/sqlite/ASV.db",
    "KJVA-osis.json": f"{RAW_BASE}/scrollmapper/bible_databases/master/sources/en/KJVA/KJVA-osis.json",
    "web.usfx.xml": f"{RAW_BASE}/seven1m/open-bibles/master/eng-web.usfx.xml",
    "strongs_greek.js": f"{RAW_BASE}/openscriptures/strongs/master/greek/strongs-greek-dictionary.js",
    "strongs_hebrew.js": f"{RAW_BASE}/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js",
    **{
        f"xref_{i}.json": (
            f"{RAW_BASE}/scrollmapper/bible_databases/master/sources/extras/cross_references_{i}.json"
        )
        for i in range(7)
    },
    "mhc.tar.gz": "https://github.com/lyteword/mhenry-concise/archive/refs/heads/master.tar.gz",
}

TRANSLATIONS = [
    ("KJV", "King James Version", 1769),
    ("ASV", "American Standard Version", 1901),
    ("WEB", "World English Bible", 2000),
]


def fetch_sources(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in SOURCES.items():
        dest = cache_dir / filename
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print(f"fetching {filename} ...")
        urllib.request.urlretrieve(url, dest)


# ----------------------------------------------------------------------
# Translation text
# ----------------------------------------------------------------------


def import_scrollmapper_sqlite(conn: sqlite3.Connection, cache_dir: Path, filename: str, table_prefix: str,
                                translation_id: int) -> None:
    """KJV.db / ASV.db each bundle 7 duplicate copies of the whole Bible
    back-to-back (a scrollmapper export quirk) - verse ids 1..31102 are the
    clean first copy; everything after that is a repeat."""
    src = sqlite3.connect(cache_dir / filename)
    src.row_factory = sqlite3.Row
    rows = src.execute(
        f"SELECT book_id, chapter, verse, text FROM {table_prefix}_verses "
        f"WHERE id BETWEEN 1 AND 31102 ORDER BY id"
    ).fetchall()
    conn.executemany(
        "INSERT INTO verses (translation_id, book_id, chapter, verse, text) VALUES (?, ?, ?, ?, ?)",
        [(translation_id, r["book_id"], r["chapter"], r["verse"], r["text"].strip()) for r in rows],
    )
    src.close()


USFX_TO_OSIS = {
    "GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh", "JDG": "Judg",
    "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs", "1CH": "1Chr", "2CH": "2Chr",
    "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job", "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl",
    "SNG": "Song", "ISA": "Isa", "JER": "Jer", "LAM": "Lam", "EZK": "Ezek", "DAN": "Dan", "HOS": "Hos",
    "JOL": "Joel", "AMO": "Amos", "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAM": "Nah", "HAB": "Hab",
    "ZEP": "Zeph", "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal", "MAT": "Matt", "MRK": "Mark", "LUK": "Luke",
    "JHN": "John", "ACT": "Acts", "ROM": "Rom", "1CO": "1Cor", "2CO": "2Cor", "GAL": "Gal", "EPH": "Eph",
    "PHP": "Phil", "COL": "Col", "1TH": "1Thess", "2TH": "2Thess", "1TI": "1Tim", "2TI": "2Tim", "TIT": "Titus",
    "PHM": "Phlm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pet", "2PE": "2Pet", "1JN": "1John", "2JN": "2John",
    "3JN": "3John", "JUD": "Jude", "REV": "Rev",
}

_USFX_TAG_RE = re.compile(r"<([^>]+)>")


def parse_usfx(path: Path) -> dict[tuple[str, int, int], str]:
    """Parses WEB's USFX XML into {(osis_code, chapter, verse): text}.
    Footnotes (<f>) and cross-ref markup (<x>) are dropped; every other tag
    is structural and its surrounding text is kept."""
    data = path.read_text(encoding="utf-8")
    verses: dict[tuple[str, int, int], str] = {}
    pos = 0
    current_book: str | None = None
    current_chapter: int | None = None
    current_verse: int | None = None
    skip_depth = 0
    buf: list[str] = []

    def flush() -> None:
        if current_book and current_verse is not None:
            text = re.sub(r"\s+", " ", "".join(buf)).strip()
            if text:
                key = (current_book, current_chapter, current_verse)
                verses[key] = text
        buf.clear()

    for m in _USFX_TAG_RE.finditer(data):
        start, end = m.span()
        if skip_depth == 0 and data[pos:start]:
            buf.append(data[pos:start])
        pos = end

        raw = m.group(1)
        self_closing = raw.endswith("/")
        is_end = raw.startswith("/")
        body = raw[1:] if is_end else (raw[:-1] if self_closing else raw)
        tag = body.split()[0] if body.split() else body
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', body))

        if is_end:
            if tag in ("f", "x"):
                skip_depth = max(0, skip_depth - 1)
            if tag == "book":
                current_book = None
        else:
            if tag == "book":
                flush()
                current_book = USFX_TO_OSIS.get(attrs.get("id", ""))
                current_chapter, current_verse = None, None
            elif tag == "c":
                flush()
                current_chapter = int(attrs.get("id", "0"))
                current_verse = None
            elif tag == "v":
                flush()
                vnum = re.match(r"\d+", attrs.get("id", "0"))
                current_verse = int(vnum.group()) if vnum else None
            elif tag == "ve":
                flush()
                current_verse = None
            elif tag in ("f", "x") and not self_closing:
                skip_depth += 1

    if skip_depth == 0 and pos < len(data):
        buf.append(data[pos:])
    flush()
    return verses


def import_web(conn: sqlite3.Connection, cache_dir: Path, translation_id: int) -> None:
    verses = parse_usfx(cache_dir / "web.usfx.xml")
    osis_to_book = {b.osis_code: b for b in CANONICAL_BOOKS}
    book_id_by_num = {b.book_num: i + 1 for i, b in enumerate(CANONICAL_BOOKS)}  # book_num == id, see import_books
    rows = []
    for (osis, chapter, verse), text in verses.items():
        book = osis_to_book.get(osis)
        if book is None:
            continue
        rows.append((translation_id, book_id_by_num[book.book_num], chapter, verse, text))
    conn.executemany(
        "INSERT INTO verses (translation_id, book_id, chapter, verse, text) VALUES (?, ?, ?, ?, ?)", rows
    )


# ----------------------------------------------------------------------
# Books / translations
# ----------------------------------------------------------------------


def import_books(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO books (id, book_num, name, abbreviation, osis_code, testament, category, chapter_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (b.book_num, b.book_num, b.name, b.abbreviation, b.osis_code, b.testament, b.category, b.chapter_count)
            for b in CANONICAL_BOOKS
        ],
    )


def import_translations(conn: sqlite3.Connection) -> dict[str, int]:
    ids = {}
    for code, name, year in TRANSLATIONS:
        cur = conn.execute(
            "INSERT INTO translations (code, name, year) VALUES (?, ?, ?)", (code, name, year)
        )
        ids[code] = cur.lastrowid
    return ids


# ----------------------------------------------------------------------
# Strong's concordance + interlinear tagging
# ----------------------------------------------------------------------

_STRONGS_TAG_RE = re.compile(r'<w lemma="([^"]*)"[^>]*>([^<]*)</w>')
_STRONGS_CODE_RE = re.compile(r"strong:([HG])0*(\d+)")

# KJVA-osis.json lists 80 books: indices 0-38 are the 39 OT books, 39-52 are
# apocrypha (not in our canon), 53-79 are the 27 NT books. Positional mapping
# sidesteps roman-numeral vs. digit book-name spelling differences entirely.
KJVA_OSIS_INDICES = list(range(0, 39)) + list(range(53, 80))


def normalize_strongs_code(raw_lemma: str) -> str | None:
    # A word can carry multiple lemma codes (e.g. "strong:H0853 strong:H01254"
    # for "created" - the untranslated direct-object marker plus the real
    # verb). The last code is consistently the semantically primary one in
    # this dataset, so prefer it over the first.
    matches = list(_STRONGS_CODE_RE.finditer(raw_lemma))
    if not matches:
        return None
    m = matches[-1]
    return f"{m.group(1)}{int(m.group(2))}"


def load_strongs_dictionary(cache_dir: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for filename, prefix in [("strongs_greek.js", "G"), ("strongs_hebrew.js", "H")]:
        text = (cache_dir / filename).read_text(encoding="utf-8")
        obj = json.loads(text[text.index("{"): text.rindex("}") + 1])
        for code, data in obj.items():
            entries[code] = {
                "language": "Greek" if prefix == "G" else "Hebrew",
                "transliteration": data.get("translit") or data.get("xlit") or "",
                "definition": data.get("strongs_def") or data.get("kjv_def") or "",
                "pronunciation": data.get("pron") or "",
            }
    return entries


def import_strongs(conn: sqlite3.Connection, cache_dir: Path, kjv_translation_id: int) -> None:
    dictionary = load_strongs_dictionary(cache_dir)
    conn.executemany(
        "INSERT OR IGNORE INTO strongs (code, language, transliteration, definition, pronunciation) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (code, d["language"], d["transliteration"], d["definition"] or "(no definition)", d["pronunciation"])
            for code, d in dictionary.items()
        ],
    )

    verse_id_lookup = {
        (r["book_id"], r["chapter"], r["verse"]): r["id"]
        for r in conn.execute(
            "SELECT id, book_id, chapter, verse FROM verses WHERE translation_id = ?", (kjv_translation_id,)
        )
    }

    osis_data = json.loads((cache_dir / "KJVA-osis.json").read_text(encoding="utf-8"))["books"]
    osis_to_book_id = {b.osis_code: b.book_num for b in CANONICAL_BOOKS}
    canonical_osis_order = [b.osis_code for b in CANONICAL_BOOKS]

    rows = []
    skipped_codes = 0
    for canonical_i, source_i in enumerate(KJVA_OSIS_INDICES):
        osis = canonical_osis_order[canonical_i]
        book_id = osis_to_book_id[osis]
        book_data = osis_data[source_i]
        for ch in book_data["chapters"]:
            chapter = ch["chapter"]
            for v in ch["verses"]:
                verse_id = verse_id_lookup.get((book_id, chapter, v["verse"]))
                if verse_id is None:
                    continue
                for word_index, m in enumerate(_STRONGS_TAG_RE.finditer(v["text"])):
                    code = normalize_strongs_code(m.group(1))
                    word = m.group(2).strip()
                    if not code or not word or code not in dictionary:
                        skipped_codes += 1
                        continue
                    rows.append((verse_id, word_index, word, code))

    conn.executemany(
        "INSERT OR IGNORE INTO verse_strongs (verse_id, word_index, word, strongs_code) VALUES (?, ?, ?, ?)",
        rows,
    )
    print(f"  strongs: {len(rows)} word tags inserted, {skipped_codes} skipped (no dictionary match)")


# ----------------------------------------------------------------------
# Cross-references
# ----------------------------------------------------------------------


def import_cross_references(conn: sqlite3.Connection, cache_dir: Path) -> None:
    book_id_by_name = {b.name: b.book_num for b in CANONICAL_BOOKS}
    rows = []
    for i in range(7):
        data = json.loads((cache_dir / f"xref_{i}.json").read_text(encoding="utf-8"))
        for entry in data["cross_references"]:
            from_book = book_id_by_name.get(entry["from_verse"]["book"])
            if from_book is None:
                continue
            for to in entry["to_verse"]:
                to_book = book_id_by_name.get(to["book"])
                if to_book is None:
                    continue
                for verse_num in range(to["verse_start"], to["verse_end"] + 1):
                    rows.append(
                        (
                            from_book,
                            entry["from_verse"]["chapter"],
                            entry["from_verse"]["verse"],
                            to_book,
                            to["chapter"],
                            verse_num,
                            entry.get("votes", 0),
                        )
                    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO cross_references
            (from_book_id, from_chapter, from_verse, to_book_id, to_chapter, to_verse, votes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    print(f"  cross_references: {len(rows)} rows inserted")


# ----------------------------------------------------------------------
# Commentary
# ----------------------------------------------------------------------

_VERSE_HEADER_RE = re.compile(r"^##\s+Verses?\s+(.+?)\s*$", re.IGNORECASE)


def _expand_verse_numbers(spec: str) -> list[int]:
    numbers: list[int] = []
    for token in spec.split(","):
        token = token.strip().replace("–", "-").replace("—", "-")
        if "-" in token:
            start, end = token.split("-", 1)
            if start.strip().isdigit() and end.strip().isdigit():
                numbers.extend(range(int(start), int(end) + 1))
        elif token.isdigit():
            numbers.append(int(token))
    return numbers


def parse_commentary_chapter(text: str) -> list[tuple[int, int, str]]:
    """Returns [(verse_start, verse_end, body), ...] for one chapter file."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]

    blocks = []
    lines = text.splitlines()
    current_range: tuple[int, int] | None = None
    current_lines: list[str] = []

    def flush():
        if current_range and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                blocks.append((current_range[0], current_range[1], body))

    for line in lines:
        header = _VERSE_HEADER_RE.match(line)
        if header:
            flush()
            nums = _expand_verse_numbers(header.group(1))
            current_range = (min(nums), max(nums)) if nums else None
            current_lines = []
        elif line.startswith("## "):
            flush()
            current_range = None
            current_lines = []
        elif current_range:
            current_lines.append(line)
    flush()
    return blocks


def import_commentary(conn: sqlite3.Connection, cache_dir: Path) -> None:
    tar_path = cache_dir / "mhc.tar.gz"
    extract_dir = cache_dir / "mhc_extracted"
    if not extract_dir.exists():
        with tarfile.open(tar_path) as tf:
            tf.extractall(extract_dir, filter="data")

    root = next(extract_dir.iterdir())
    rows = []
    for book in CANONICAL_BOOKS:
        slug = book.name.lower().replace(" ", "-")
        book_dir = root / slug
        if not book_dir.is_dir():
            continue
        for chapter_file in book_dir.glob("chapter-*.md"):
            m = re.search(r"chapter-(\d+)\.md", chapter_file.name)
            if not m:
                continue
            chapter = int(m.group(1))
            text = chapter_file.read_text(encoding="utf-8")
            for verse_start, verse_end, body in parse_commentary_chapter(text):
                rows.append((book.book_num, chapter, verse_start, verse_end, "Matthew Henry", body))
    conn.executemany(
        """
        INSERT INTO commentaries (book_id, chapter, verse_start, verse_end, author, text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    print(f"  commentary: {len(rows)} blocks inserted")


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------


def run_import(cache_dir: str, db_path: Path | None = None) -> None:
    from bible_tui.config import Config

    cache = Path(cache_dir)
    fetch_sources(cache)

    if db_path is None:
        db_path = Config.load().db_path
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

    conn = connect(db_path)
    init_schema(conn)

    print("importing books/translations ...")
    import_books(conn)
    translation_ids = import_translations(conn)
    conn.commit()

    print("importing KJV ...")
    import_scrollmapper_sqlite(conn, cache, "KJV.db", "KJV", translation_ids["KJV"])
    conn.commit()

    print("importing ASV ...")
    import_scrollmapper_sqlite(conn, cache, "ASV.db", "ASV", translation_ids["ASV"])
    conn.commit()

    print("importing WEB ...")
    import_web(conn, cache, translation_ids["WEB"])
    conn.commit()

    print("importing Strong's concordance ...")
    import_strongs(conn, cache, translation_ids["KJV"])
    conn.commit()

    print("importing cross-references ...")
    import_cross_references(conn, cache)
    conn.commit()

    print("importing commentary ...")
    import_commentary(conn, cache)
    conn.commit()

    conn.execute("INSERT INTO verses_fts(verses_fts) VALUES ('rebuild')")
    conn.commit()
    conn.close()
    print(f"done: {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default=str(Path(__file__).parent / "raw_cache"))
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()
    run_import(args.cache_dir, Path(args.db_path) if args.db_path else None)


if __name__ == "__main__":
    main()
