PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- REFERENCE DATA (populated once by scripts/import_data.py, read-only at runtime)
-- ============================================================

CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,        -- 'KJV', 'WEB', 'ASV'
    name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    is_public_domain BOOLEAN NOT NULL DEFAULT 1,
    year INTEGER
);

-- Canonical book list, one row per book regardless of translation.
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY,
    book_num INTEGER NOT NULL UNIQUE,   -- 1-66, canonical order
    name TEXT NOT NULL,                 -- 'Genesis'
    abbreviation TEXT NOT NULL,         -- 'Gen'
    osis_code TEXT NOT NULL UNIQUE,     -- 'Gen', matches OSIS standard
    testament TEXT NOT NULL CHECK(testament IN ('OT', 'NT')),
    category TEXT NOT NULL,             -- 'Law', 'History', 'Poetry', 'Major Prophets',
                                         -- 'Minor Prophets', 'Gospels', 'Acts', 'Epistles', 'Apocalyptic'
    chapter_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS verses (
    id INTEGER PRIMARY KEY,
    translation_id INTEGER NOT NULL REFERENCES translations(id),
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    text TEXT NOT NULL,
    UNIQUE(translation_id, book_id, chapter, verse)
);

CREATE INDEX IF NOT EXISTS idx_verses_lookup ON verses(translation_id, book_id, chapter, verse);
CREATE INDEX IF NOT EXISTS idx_verses_book_chapter ON verses(translation_id, book_id, chapter);

-- FTS5 external-content table. Kept in sync by the triggers below.
CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
    text,
    content='verses',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS verses_ai AFTER INSERT ON verses BEGIN
    INSERT INTO verses_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS verses_ad AFTER DELETE ON verses BEGIN
    INSERT INTO verses_fts(verses_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS verses_au AFTER UPDATE ON verses BEGIN
    INSERT INTO verses_fts(verses_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO verses_fts(rowid, text) VALUES (new.id, new.text);
END;

-- Strong's concordance, keyed off KJV verses specifically (Strong's tagging
-- is translation-specific to KJV's exact wording; only the KJV verse rows
-- get verse_strongs entries).
CREATE TABLE IF NOT EXISTS strongs (
    code TEXT PRIMARY KEY,            -- 'H1234' or 'G1234'
    language TEXT NOT NULL CHECK(language IN ('Hebrew', 'Greek')),
    transliteration TEXT,
    definition TEXT NOT NULL,
    pronunciation TEXT
);

CREATE TABLE IF NOT EXISTS verse_strongs (
    verse_id INTEGER NOT NULL REFERENCES verses(id),
    word_index INTEGER NOT NULL,      -- 0-based position in verse
    word TEXT NOT NULL,               -- the English word as it appears
    strongs_code TEXT NOT NULL REFERENCES strongs(code),
    PRIMARY KEY (verse_id, word_index)
);

CREATE INDEX IF NOT EXISTS idx_verse_strongs_verse ON verse_strongs(verse_id);

-- Cross-references and commentary are stored against a translation-independent
-- (book_id, chapter, verse) address rather than a verses.id FK. verses.id is
-- scoped per-translation (see UNIQUE(translation_id, book_id, chapter, verse)
-- above), so an FK to it would tie this reference data to whichever
-- translation happened to be active at import time and force a join through
-- a second translation's verse rows to resolve it for any other translation.
-- Keying off the triple directly sidesteps that translation coupling entirely.
CREATE TABLE IF NOT EXISTS cross_references (
    from_book_id INTEGER NOT NULL REFERENCES books(id),
    from_chapter INTEGER NOT NULL,
    from_verse INTEGER NOT NULL,
    to_book_id INTEGER NOT NULL REFERENCES books(id),
    to_chapter INTEGER NOT NULL,
    to_verse INTEGER NOT NULL,
    votes INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (from_book_id, from_chapter, from_verse, to_book_id, to_chapter, to_verse)
);

CREATE INDEX IF NOT EXISTS idx_xref_from ON cross_references(from_book_id, from_chapter, from_verse, votes DESC);

CREATE TABLE IF NOT EXISTS commentaries (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse_start INTEGER NOT NULL,
    verse_end INTEGER NOT NULL,
    author TEXT NOT NULL,             -- 'Matthew Henry'
    text TEXT NOT NULL,
    source_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_commentary_lookup ON commentaries(book_id, chapter, verse_start, verse_end);

-- ============================================================
-- USER DATA (read-write at runtime)
-- ============================================================
--
-- Bookmarks/notes/highlights/last_position address a verse by
-- (book_id, chapter, verse) rather than verses.id for the same reason
-- cross_references does: a verse the user marked while reading KJV should
-- still show as marked when they switch to ASV or WEB.

CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    label TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(book_id, chapter, verse)
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notes_verse ON notes(book_id, chapter, verse);

CREATE TABLE IF NOT EXISTS highlights (
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    color TEXT NOT NULL DEFAULT 'yellow',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (book_id, chapter, verse)
);

-- Bookmark folders, tags, favourites and reading lists: all address a verse
-- by (book_id, chapter, verse), the same translation-independent convention
-- as bookmarks/notes/highlights above, for the same reason.

CREATE TABLE IF NOT EXISTS bookmark_folders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- bookmarks.folder_id is added by a guarded migration in data/database.py,
-- not here: ALTER TABLE ADD COLUMN isn't idempotent the way CREATE TABLE IF
-- NOT EXISTS is, so it can't live in this script without breaking every
-- launch after the first one against an already-migrated database.

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS verse_tags (
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (book_id, chapter, verse, tag_id)
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (note_id, tag_id)
);

-- Same shape as highlights, deliberately: a favourite is a distinct concept
-- (a personal shortlist) from a highlight (a visual reading aid), but the
-- storage need is identical - one flag per verse, on or off.
CREATE TABLE IF NOT EXISTS favourites (
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (book_id, chapter, verse)
);

CREATE TABLE IF NOT EXISTS reading_lists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reading_list_items (
    id INTEGER PRIMARY KEY,
    list_id INTEGER NOT NULL REFERENCES reading_lists(id),
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reading_list_items_list ON reading_list_items(list_id);

CREATE TABLE IF NOT EXISTS reading_plans (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    plan_type TEXT NOT NULL,          -- 'one_year', 'nt_90', 'custom'
    start_date TEXT NOT NULL,         -- ISO date
    active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS plan_entries (
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES reading_plans(id),
    day_number INTEGER NOT NULL,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter_start INTEGER NOT NULL,
    chapter_end INTEGER NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plan_entries_plan_day ON plan_entries(plan_id, day_number);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL               -- JSON-encoded
);

CREATE TABLE IF NOT EXISTS last_position (
    id INTEGER PRIMARY KEY CHECK(id = 1),  -- singleton row
    translation_code TEXT NOT NULL,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL
);

-- One row per chapter actually read, which is what every statistic on the
-- stats screen is derived from. Storing events rather than running totals
-- means a number that looks wrong can be traced back to the readings that
-- produced it, and new statistics can be added later without a backfill.
--
-- read_on is the *local* date, denormalised from started_at, because every
-- streak and calendar question is asked in the reader's own timezone and
-- deriving it in SQL would push those queries onto UTC.
CREATE TABLE IF NOT EXISTS reading_events (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chapter INTEGER NOT NULL,
    translation_code TEXT NOT NULL,
    read_on TEXT NOT NULL,             -- ISO date, local
    started_at TEXT NOT NULL,          -- ISO timestamp, local
    seconds INTEGER NOT NULL DEFAULT 0,
    verses INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_reading_events_day ON reading_events(read_on);
CREATE INDEX IF NOT EXISTS idx_reading_events_place ON reading_events(book_id, chapter);
