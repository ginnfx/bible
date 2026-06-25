from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    book_num: int
    name: str
    abbreviation: str
    osis_code: str
    testament: str  # 'OT' or 'NT'
    category: str
    chapter_count: int


# Canonical 66-book list in Bible order. This is the single source of truth
# for book metadata; the importer writes these rows into the `books` table
# and nothing else ever needs to hardcode chapter counts or categories again.
CANONICAL_BOOKS: list[Book] = [
    Book(1, "Genesis", "Gen", "Gen", "OT", "Law", 50),
    Book(2, "Exodus", "Exod", "Exod", "OT", "Law", 40),
    Book(3, "Leviticus", "Lev", "Lev", "OT", "Law", 27),
    Book(4, "Numbers", "Num", "Num", "OT", "Law", 36),
    Book(5, "Deuteronomy", "Deut", "Deut", "OT", "Law", 34),
    Book(6, "Joshua", "Josh", "Josh", "OT", "History", 24),
    Book(7, "Judges", "Judg", "Judg", "OT", "History", 21),
    Book(8, "Ruth", "Ruth", "Ruth", "OT", "History", 4),
    Book(9, "1 Samuel", "1Sam", "1Sam", "OT", "History", 31),
    Book(10, "2 Samuel", "2Sam", "2Sam", "OT", "History", 24),
    Book(11, "1 Kings", "1Kgs", "1Kgs", "OT", "History", 22),
    Book(12, "2 Kings", "2Kgs", "2Kgs", "OT", "History", 25),
    Book(13, "1 Chronicles", "1Chr", "1Chr", "OT", "History", 29),
    Book(14, "2 Chronicles", "2Chr", "2Chr", "OT", "History", 36),
    Book(15, "Ezra", "Ezra", "Ezra", "OT", "History", 10),
    Book(16, "Nehemiah", "Neh", "Neh", "OT", "History", 13),
    Book(17, "Esther", "Esth", "Esth", "OT", "History", 10),
    Book(18, "Job", "Job", "Job", "OT", "Poetry", 42),
    Book(19, "Psalms", "Ps", "Ps", "OT", "Poetry", 150),
    Book(20, "Proverbs", "Prov", "Prov", "OT", "Poetry", 31),
    Book(21, "Ecclesiastes", "Eccl", "Eccl", "OT", "Poetry", 12),
    Book(22, "Song of Solomon", "Song", "Song", "OT", "Poetry", 8),
    Book(23, "Isaiah", "Isa", "Isa", "OT", "Major Prophets", 66),
    Book(24, "Jeremiah", "Jer", "Jer", "OT", "Major Prophets", 52),
    Book(25, "Lamentations", "Lam", "Lam", "OT", "Major Prophets", 5),
    Book(26, "Ezekiel", "Ezek", "Ezek", "OT", "Major Prophets", 48),
    Book(27, "Daniel", "Dan", "Dan", "OT", "Major Prophets", 12),
    Book(28, "Hosea", "Hos", "Hos", "OT", "Minor Prophets", 14),
    Book(29, "Joel", "Joel", "Joel", "OT", "Minor Prophets", 3),
    Book(30, "Amos", "Amos", "Amos", "OT", "Minor Prophets", 9),
    Book(31, "Obadiah", "Obad", "Obad", "OT", "Minor Prophets", 1),
    Book(32, "Jonah", "Jonah", "Jonah", "OT", "Minor Prophets", 4),
    Book(33, "Micah", "Mic", "Mic", "OT", "Minor Prophets", 7),
    Book(34, "Nahum", "Nah", "Nah", "OT", "Minor Prophets", 3),
    Book(35, "Habakkuk", "Hab", "Hab", "OT", "Minor Prophets", 3),
    Book(36, "Zephaniah", "Zeph", "Zeph", "OT", "Minor Prophets", 3),
    Book(37, "Haggai", "Hag", "Hag", "OT", "Minor Prophets", 2),
    Book(38, "Zechariah", "Zech", "Zech", "OT", "Minor Prophets", 14),
    Book(39, "Malachi", "Mal", "Mal", "OT", "Minor Prophets", 4),
    Book(40, "Matthew", "Matt", "Matt", "NT", "Gospels", 28),
    Book(41, "Mark", "Mark", "Mark", "NT", "Gospels", 16),
    Book(42, "Luke", "Luke", "Luke", "NT", "Gospels", 24),
    Book(43, "John", "John", "John", "NT", "Gospels", 21),
    Book(44, "Acts", "Acts", "Acts", "NT", "Acts", 28),
    Book(45, "Romans", "Rom", "Rom", "NT", "Epistles", 16),
    Book(46, "1 Corinthians", "1Cor", "1Cor", "NT", "Epistles", 16),
    Book(47, "2 Corinthians", "2Cor", "2Cor", "NT", "Epistles", 13),
    Book(48, "Galatians", "Gal", "Gal", "NT", "Epistles", 6),
    Book(49, "Ephesians", "Eph", "Eph", "NT", "Epistles", 6),
    Book(50, "Philippians", "Phil", "Phil", "NT", "Epistles", 4),
    Book(51, "Colossians", "Col", "Col", "NT", "Epistles", 4),
    Book(52, "1 Thessalonians", "1Thess", "1Thess", "NT", "Epistles", 5),
    Book(53, "2 Thessalonians", "2Thess", "2Thess", "NT", "Epistles", 3),
    Book(54, "1 Timothy", "1Tim", "1Tim", "NT", "Epistles", 6),
    Book(55, "2 Timothy", "2Tim", "2Tim", "NT", "Epistles", 4),
    Book(56, "Titus", "Titus", "Titus", "NT", "Epistles", 3),
    Book(57, "Philemon", "Phlm", "Phlm", "NT", "Epistles", 1),
    Book(58, "Hebrews", "Heb", "Heb", "NT", "Epistles", 13),
    Book(59, "James", "Jas", "Jas", "NT", "Epistles", 5),
    Book(60, "1 Peter", "1Pet", "1Pet", "NT", "Epistles", 5),
    Book(61, "2 Peter", "2Pet", "2Pet", "NT", "Epistles", 3),
    Book(62, "1 John", "1John", "1John", "NT", "Epistles", 5),
    Book(63, "2 John", "2John", "2John", "NT", "Epistles", 1),
    Book(64, "3 John", "3John", "3John", "NT", "Epistles", 1),
    Book(65, "Jude", "Jude", "Jude", "NT", "Epistles", 1),
    Book(66, "Revelation", "Rev", "Rev", "NT", "Apocalyptic", 22),
]

BOOKS_BY_OSIS: dict[str, Book] = {b.osis_code: b for b in CANONICAL_BOOKS}
