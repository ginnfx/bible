"""Forgiving book-name matching.

The books table stores one canonical name and one abbreviation each, which
means perfectly ordinary spellings - ``Psalm``, ``jn``, ``song of songs``,
``rev`` - miss. This table maps the common alternatives onto the canonical
name so a reference lookup succeeds without the user having to guess which
spelling the database happens to hold.

Keys are lower-cased and stripped of internal spacing by
:func:`normalise_book_query`, so ``1 Cor``, ``1cor`` and ``1  COR`` all hit
the same entry.
"""

from __future__ import annotations

_ALIASES: dict[str, str] = {
    # Singular/plural and word-order variants of the canonical names.
    "psalm": "Psalms",
    "psalter": "Psalms",
    "song of songs": "Song of Solomon",
    "songofsongs": "Song of Solomon",
    "canticles": "Song of Solomon",
    "revelations": "Revelation",
    "apocalypse": "Revelation",
    "acts of the apostles": "Acts",
    "ecclesiastes": "Ecclesiastes",
    # Short forms people actually type.
    "gen": "Genesis",
    "ex": "Exodus",
    "exo": "Exodus",
    "lev": "Leviticus",
    "num": "Numbers",
    "deut": "Deuteronomy",
    "dt": "Deuteronomy",
    "josh": "Joshua",
    "judg": "Judges",
    "jdg": "Judges",
    "sam1": "1 Samuel",
    "kgs1": "1 Kings",
    "chron1": "1 Chronicles",
    "neh": "Nehemiah",
    "esth": "Esther",
    "ps": "Psalms",
    "psa": "Psalms",
    "pss": "Psalms",
    "prov": "Proverbs",
    "prv": "Proverbs",
    "eccl": "Ecclesiastes",
    "ecc": "Ecclesiastes",
    "song": "Song of Solomon",
    "sos": "Song of Solomon",
    "isa": "Isaiah",
    "jer": "Jeremiah",
    "lam": "Lamentations",
    "ezek": "Ezekiel",
    "eze": "Ezekiel",
    "dan": "Daniel",
    "hos": "Hosea",
    "obad": "Obadiah",
    "jon": "Jonah",
    "mic": "Micah",
    "nah": "Nahum",
    "hab": "Habakkuk",
    "zeph": "Zephaniah",
    "hag": "Haggai",
    "zech": "Zechariah",
    "mal": "Malachi",
    "matt": "Matthew",
    "mt": "Matthew",
    "mk": "Mark",
    "mrk": "Mark",
    "lk": "Luke",
    "jn": "John",
    "jhn": "John",
    "rom": "Romans",
    "cor1": "1 Corinthians",
    "gal": "Galatians",
    "eph": "Ephesians",
    "phil": "Philippians",
    "php": "Philippians",
    "col": "Colossians",
    "thess1": "1 Thessalonians",
    "tim1": "1 Timothy",
    "phlm": "Philemon",
    "phm": "Philemon",
    "heb": "Hebrews",
    "jas": "James",
    "jm": "James",
    "pet1": "1 Peter",
    "rev": "Revelation",
    "rv": "Revelation",
}

# Numbered books: "1 John", "1john", "1 jn", "i john"… all resolve. Built
# rather than typed out, so adding a stem covers every ordinal at once.
_NUMBERED_STEMS: dict[str, list[str]] = {
    "Samuel": ["sam", "sa", "sm"],
    "Kings": ["kings", "kgs", "kg", "ki"],
    "Chronicles": ["chronicles", "chron", "chr", "ch"],
    "Corinthians": ["corinthians", "cor", "co"],
    "Thessalonians": ["thessalonians", "thess", "thes", "th"],
    "Timothy": ["timothy", "tim", "ti"],
    "Peter": ["peter", "pet", "pe", "pt"],
    "John": ["john", "jn", "jhn"],
}

_ORDINAL_PREFIXES = {"1": "1", "2": "2", "3": "3", "i": "1", "ii": "2", "iii": "3"}

for _book, _stems in _NUMBERED_STEMS.items():
    for _stem in _stems:
        for _typed, _canonical_number in _ORDINAL_PREFIXES.items():
            _ALIASES[f"{_typed}{_stem}"] = f"{_canonical_number} {_book}"

# 1/2/3 John's stems collide with the plain Gospel of John; the bare stems
# must stay pointed at the Gospel.
_ALIASES["john"] = "John"
_ALIASES["jn"] = "John"
_ALIASES["jhn"] = "John"


def normalise_book_query(query: str) -> str:
    """Map a typed book name onto its canonical form, or return it unchanged.

    Spacing and case are ignored, so ``1 Cor``, ``1cor`` and ``I  COR`` are
    the same lookup.
    """
    collapsed = " ".join(query.strip().lower().split())
    return (
        _ALIASES.get(collapsed)
        or _ALIASES.get(collapsed.replace(" ", ""))
        or query.strip()
    )
