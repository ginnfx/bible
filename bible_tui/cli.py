"""Command-line entry point.

Two shapes, following christ-cli: bare ``bible`` launches the full TUI, and
subcommands (``read``, ``search``, ``random``, ``today``) answer a single
question and exit. Those subcommands are pipe-aware - a terminal gets a
rendered card, a pipe gets plain text - so ``bible read John 3:16 | pbcopy``
does the obvious thing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

from .models.verse import Verse

PROG = "bible"

#: Subcommands, used to tell `bible read ...` from `bible "John 3:16"`.
_COMMANDS = {
    "read",
    "search",
    "random",
    "today",
    "intro",
    "import-data",
    "backup",
    "restore",
    "check",
    "stats",
    "print",
}


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    args = parser.parse_args(_normalise(argv))

    handlers = {
        "read": _cmd_read,
        "search": _cmd_search,
        "random": _cmd_random,
        "today": _cmd_today,
        "intro": _cmd_intro,
        "import-data": _cmd_import,
        "backup": _cmd_backup,
        "restore": _cmd_restore,
        "check": _cmd_check,
        "stats": _cmd_stats,
        "print": _cmd_print,
        None: _cmd_tui,
    }
    handlers[args.command](args)


def _normalise(argv: list[str]) -> list[str]:
    """Keep the bare-reference form working: ``bible "John 3:16"`` means
    ``bible read "John 3:16"``, since that is what anyone types first.
    ``bible bible://John/3/16`` (an OS URL handler invocation, or someone
    testing one by hand) means the same thing, converted first.

    Only a *leading* positional is rewritten - anything after a flag could be
    that flag's value, and guessing there would mangle ``read x -t ASV``.
    """
    if argv and argv[0].lower().startswith("bible:"):
        from .data.reference_parser import parse_bible_url

        reference = parse_bible_url(argv[0])
        if reference is not None:
            return ["read", reference] + argv[1:]
    if argv and not argv[0].startswith("-") and argv[0] not in _COMMANDS:
        return ["read"] + argv
    return argv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG, description="A Bible reader for the terminal."
    )
    parser.add_argument(
        "--banner", action="store_true", help="Play the startup animation on launch"
    )
    parser.add_argument(
        "--no-banner", action="store_true", help="Skip the startup animation"
    )
    parser.add_argument(
        "--profile",
        help=(
            "Use a separate config and database (default: $BIBLE_TUI_PROFILE, "
            "else the default profile)"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    read = sub.add_parser("read", help='Read a verse, range, or chapter (e.g. "John 3:16")')
    read.add_argument("reference", nargs="+", help='e.g. "John 3:16", "Genesis 1", "1cor 13:4-7"')
    _add_translation(read)

    search = sub.add_parser("search", help="Search the Bible for a phrase")
    search.add_argument("query", nargs="+")
    search.add_argument("--limit", type=int, default=20, help="Maximum results (default: 20)")
    _add_translation(search)

    _add_translation(sub.add_parser("random", help="Display a random verse"))
    _add_translation(sub.add_parser("today", help="Show today's verse of the day"))

    sub.add_parser("intro", help="Replay the startup animation")

    imp = sub.add_parser("import-data", help="Run the one-time data import")
    imp.add_argument("source_dir")

    backup = sub.add_parser("backup", help="Copy your database somewhere safe")
    backup.add_argument(
        "path",
        nargs="?",
        help="Where to write it (default: a dated file in ~/Documents)",
    )
    backup.add_argument(
        "--personal",
        action="store_true",
        help="Write only your bookmarks, notes, highlights and plans, as JSON",
    )

    restore = sub.add_parser("restore", help="Restore from a backup made with `bible backup`")
    restore.add_argument("path")
    restore.add_argument(
        "--replace",
        action="store_true",
        help="For a personal archive: discard current work instead of merging",
    )

    sub.add_parser("stats", help="Show your reading record")

    prnt = sub.add_parser("print", help="Print a verse, range, or chapter via CUPS")
    prnt.add_argument("reference", nargs="+", help='e.g. "John 3:16", "Genesis 1"')
    _add_translation(prnt)

    check = sub.add_parser("check", help="Check the database for damage")
    check.add_argument(
        "--thorough",
        action="store_true",
        help="Cross-reference every index (slower, catches more)",
    )

    return parser


def _add_translation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-t",
        "--translation",
        help="Translation code (default: the one selected in the TUI, else KJV)",
    )


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------


def _cmd_tui(args: argparse.Namespace) -> None:
    _launch(reference=None, force_banner=_banner_choice(args), profile=getattr(args, "profile", None))


def _cmd_intro(args: argparse.Namespace) -> None:
    _launch(reference=None, force_banner=True, profile=getattr(args, "profile", None))


def _cmd_import(args: argparse.Namespace) -> None:
    from scripts.import_data import run_import

    run_import(args.source_dir)


def _resolve_verses(reference_words: list[str], context: "_Context") -> tuple[list[Verse], str]:
    """Shared reference resolution behind ``read`` and ``print``: parse the
    words, find the book, pull the chapter, narrow to a verse range. Returns
    the verses plus a title suitable for a page heading."""
    from .data.reference_parser import parse_reference

    raw = " ".join(reference_words)
    parsed = parse_reference(raw)
    if parsed is None:
        _die(f'Could not parse "{raw}" as a reference. Try "John 3:16" or "Genesis 1".')

    book = context.repo.get_book_by_name_or_abbrev(parsed.book_query)
    if book is None:
        suggestions = context.repo.suggest_books(parsed.book_query)
        hint = f' Did you mean {", ".join(suggestions)}?' if suggestions else ""
        _die(f'Unknown book "{parsed.book_query}".{hint}')

    # No chapter at all means the whole first chapter; a chapter with no
    # verse means that whole chapter. Both are what people expect.
    chapter = parsed.chapter or 1
    verses = context.repo.get_chapter(book["id"], chapter, context.translation)
    if not verses:
        _die(f"{book['name']} {chapter} is not available in {context.translation}.")

    title = f"{book['name']} {chapter}"
    if parsed.verse_start:
        end = parsed.verse_end or parsed.verse_start
        verses = [v for v in verses if parsed.verse_start <= v.verse <= end]
        if not verses:
            _die(f"No such verse in {book['name']} {chapter}.")
        title = f"{title}:{parsed.verse_start}" + (f"-{end}" if end != parsed.verse_start else "")
    return verses, title


def _cmd_read(args: argparse.Namespace) -> None:
    context = _open_context(args)
    verses, _title = _resolve_verses(args.reference, context)
    # Launching the interactive reader for a whole chapter would be a
    # surprise; `bible` with no arguments is where browsing lives.
    _present(verses, context)


def _cmd_print(args: argparse.Namespace) -> None:
    from .services import print_service

    context = _open_context(args)
    verses, title = _resolve_verses(args.reference, context)
    try:
        print_service.print_verses(verses, context.translation, title)
    except print_service.PrintUnavailable as error:
        _die(str(error))
    print(f"Sent {title} to the printer.")


def _cmd_search(args: argparse.Namespace) -> None:
    from .services.search_service import SearchService

    context = _open_context(args)
    query = " ".join(args.query)
    outcome = SearchService(context.repo).search(
        query, context.translation, limit=max(1, args.limit)
    )
    if not outcome.results:
        print(f'No results for "{query}".')
        return

    if outcome.corrections:
        swaps = ", ".join(f"{a} -> {b}" for a, b in outcome.corrections.items())
        print(f"No exact match; searched instead for {swaps}.\n")

    print(f'{len(outcome.results)} result(s) for "{query}":\n')
    for verse in outcome.results:
        print(f"  {verse.reference} - {verse.text}")


def _cmd_random(args: argparse.Namespace) -> None:
    context = _open_context(args)
    verse_id = context.repo.random_verse_id(context.translation)
    _present_single(verse_id, context)


def _cmd_today(args: argparse.Namespace) -> None:
    context = _open_context(args)
    today = dt.date.today().isoformat()
    verse_id = context.repo.verse_of_day_id(context.translation, today)
    _present_single(verse_id, context)


def _cmd_backup(args: argparse.Namespace) -> None:
    from pathlib import Path

    from .services.backup_service import (
        BackupError,
        BackupService,
        default_archive_path,
        default_snapshot_path,
    )

    context = _open_context(args)
    service = BackupService(context.conn)
    chosen = Path(args.path).expanduser() if args.path else None

    try:
        if args.personal:
            path = service.write_archive(chosen or default_archive_path())
            print(f"Your bookmarks, notes, highlights and plans are in {path}.")
        else:
            path = service.snapshot(chosen or default_snapshot_path())
            print(f"Backed up to {path}.")
    except BackupError as error:
        _die(f"Backup failed: {error}")


def _cmd_restore(args: argparse.Namespace) -> None:
    from pathlib import Path

    from .services.backup_service import BackupError, BackupService

    context = _open_context(args)
    service = BackupService(context.conn)
    path = Path(args.path).expanduser()

    try:
        if path.suffix.lower() == ".json":
            restored = service.read_archive(path, replace=args.replace)
            if not restored:
                print("Nothing in that archive to restore.")
                return
            summary = ", ".join(f"{count} {table}" for table, count in restored.items())
            print(f"Restored {summary}.")
        else:
            service.restore_snapshot(path)
            print(f"Restored from {path}.")
    except BackupError as error:
        _die(f"Restore failed: {error}")


def _cmd_stats(args: argparse.Namespace) -> None:
    from .services.stats_service import StatsService

    context = _open_context(args)
    stats = StatsService(context.conn)
    totals = stats.totals()
    if not totals.chapters:
        print("Nothing recorded yet - read a chapter and it will show up here.")
        return

    coverage = stats.coverage()
    streak = stats.streak()
    print(f"  {coverage.percent:.1f}% of the Bible read")
    print(f"  Chapters      {coverage.chapters_read} of {coverage.chapters_total}")
    print(f"  Books done    {coverage.books_complete} of {len(coverage.books)}")
    print(f"  Time reading  {totals.describe_time()} over {totals.days} day(s)")
    print(f"  Streak        {streak.describe()} (longest {streak.longest})")
    print(f"  {stats.pace()}")

    most_read = stats.most_read(3)
    if most_read:
        print("\n  Most read: " + ", ".join(f"{n} ({c})" for n, c in most_read))


def _cmd_check(args: argparse.Namespace) -> None:
    from .services.backup_service import BackupService

    context = _open_context(args)
    report = BackupService(context.conn).check(thorough=args.thorough)
    print(report.summary())
    if not report.ok:
        for problem in report.problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            f"\nRestore a backup with `{PROG} restore <path>`, "
            f"or re-import scripture with `{PROG} import-data <source>`.",
            file=sys.stderr,
        )
        raise SystemExit(1)


# ----------------------------------------------------------------------
# Shared plumbing
# ----------------------------------------------------------------------


class _Context:
    """The database handle and resolved translation a one-shot command needs."""

    def __init__(self, args: argparse.Namespace) -> None:
        import os

        from .config import PROFILE_ENV_VAR, Config
        from .data.database import connect, init_schema
        from .data.repository import BibleRepository

        profile = getattr(args, "profile", None) or os.environ.get(PROFILE_ENV_VAR)
        self.config = Config.load(profile)
        self.conn = connect(self.config.db_path)
        init_schema(self.conn)
        self.repo = BibleRepository(self.conn)
        self.translation = getattr(args, "translation", None) or self.config.translation_code


def _open_context(args: argparse.Namespace) -> _Context:
    return _Context(args)


def _present_single(verse_id: int | None, context: _Context) -> None:
    if verse_id is None:
        _die(f"No verses found for {context.translation} - run `{PROG} import-data <source>` first.")
    verse = context.repo.get_verse_by_id(verse_id)
    if verse is None:
        _die("Verse lookup failed.")
    _present([verse], context)


def _present(verses: list[Verse], context: _Context) -> None:
    """A terminal gets the rendered card; a pipe gets plain text."""
    if sys.stdout.isatty():
        from .ui.screens.verse_card import VerseCardApp

        VerseCardApp(verses, context.translation, context.config.theme).run()
        return
    for verse in verses:
        print(f"{verse.reference} - {verse.text} ({context.translation})")


def _launch(reference: str | None, force_banner: bool | None, profile: str | None = None) -> None:
    import os

    from .app import BibleApp
    from .config import PROFILE_ENV_VAR

    profile = profile or os.environ.get(PROFILE_ENV_VAR)
    BibleApp(initial_reference=reference, force_banner=force_banner, profile=profile).run()


def _banner_choice(args: argparse.Namespace) -> bool | None:
    """None means "decide from the saved session" - the intro plays once."""
    if getattr(args, "no_banner", False):
        return False
    if getattr(args, "banner", False):
        return True
    return None


def _die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
