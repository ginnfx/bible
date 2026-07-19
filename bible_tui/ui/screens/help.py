"""Full keybinding reference, opened with ``?``.

Sectioned the way christ-cli's help popup is - the status bar carries the
nine hints you reach for constantly, and everything else lives here.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Navigation",
        [
            ("←/→  h/l", "switch panels (Books · Chapters · Scripture)"),
            ("↑/↓  j/k", "move in lists; verse cursor in Scripture"),
            ("enter", "open book / load chapter / open study"),
            ("[  ]", "previous / next chapter (rolls into the next book)"),
            ("pgup/pgdn", "scroll the focused panel a page at a time"),
            ("g", "go to a reference (e.g. \"1 cor 13:4\")"),
            ("alt+←/→", "history back / forward"),
            ("home/end", "jump to either end of the focused panel"),
            ("tab", "narrow the Books panel: testament, then category"),
        ],
    ),
    (
        "Reading",
        [
            ("p", "toggle verse-per-line ⇄ paragraph view"),
            ("f", "focus mode - hide everything but scripture"),
            ("#", "show / hide verse numbers"),
            ("\\", "compare this verse across all translations"),
            ("r", "jump to a random verse"),
            ("v", "choose translation"),
            ("t", "cycle themes"),
            ("R", "reading modes - memorise, quiz, sermon, prayer, academic and more"),
            ("D", "display settings - wrap, spacing, low-vision, heading, columns"),
        ],
    ),
    (
        "Copy and export",
        [
            ("y  or  c", "copy the selected verse"),
            ("Y  or  C", "start a verse range; extend with j/k, Y copies"),
            ("escape", "cancel the range selection"),
            ("e", "export the chapter (or range) to a file"),
        ],
    ),
    (
        "Study & annotation",
        [
            ("s", "study view: interlinear, cross-refs, commentary, dictionary"),
            ("ctrl+t", "browse topics"),
            ("b", "toggle bookmark"),
            ("B", "name this bookmark"),
            ("ctrl+b", "browse bookmarks - filter, o reorder, l label, f folder, t tag, v favourites, d delete, ctrl+l lists"),
            ("*", "toggle favourite"),
            ("L", "add to a reading list"),
            ("m", "cycle highlight colour"),
            ("n", "add / edit a note (ctrl+p previews as Markdown)"),
            ("ctrl+p", "print the chapter (or range)"),
        ],
    ),
    (
        "Search",
        [
            ("/  or  ctrl+f", "open search"),
            ("tab", "narrow the scope: testament, then category"),
            ("ctrl+r", "saved and recent searches"),
            ("ctrl+s", "save the current search by name"),
            ("ctrl+n", "refine within the current results"),
            ("ctrl+e", "export the results"),
        ],
    ),
    (
        "Search syntax",
        [
            ('"exact phrase"', "match the words together, in order"),
            ("one OR two", "either word"),
            ("word -other", "exclude the second word"),
            ("begin*", "any word starting with this"),
            ("a NEAR/5 b", "both words within five words of each other"),
        ],
    ),
    (
        "Plans and progress",
        [
            ("P", "reading plans - n new, c catch up, s switch, x restart"),
            ("S", "your reading record"),
        ],
    ),
    (
        "Other",
        [
            ("?", "toggle this help"),
            ("q q", "quit (press q twice)"),
        ],
    ),
]

_NOTES = [
    "Reading past the end of a chapter carries on into the next one.",
    "In paragraph view, y copies the whole chapter.",
    "Copying works over SSH too (OSC 52).",
    "Search operators must be UPPERCASE, so the word \"not\" stays searchable.",
    "Chapters you linger on are counted towards your record; ones you flip past aren't.",
    'CLI:  bible read "John 3:16"  ·  bible search "..."  ·  bible random',
]


def _render() -> str:
    lines: list[str] = []
    for title, rows in _SECTIONS:
        lines.append(f"[b $accent]{title}[/]")
        lines.extend(f"  [b $primary]{key:<14}[/]{desc}" for key, desc in rows)
        lines.append("")
    lines.extend(f"[$text-disabled]{note}[/]" for note in _NOTES)
    return "\n".join(lines)


class HelpModal(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
        background: $background 60%;
    }
    HelpModal #help-box {
        width: 72;
        height: auto;
        max-height: 90%;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    HelpModal #help-scroll {
        height: auto;
        max-height: 30;
        scrollbar-size-vertical: 1;
    }
    HelpModal #help-footer {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
        Binding("q", "close", "Close", show=False),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            with VerticalScroll(id="help-scroll"):
                yield Static(_render(), markup=True)
            yield Static("Esc or ? to close", id="help-footer")

    def on_mount(self) -> None:
        self.query_one("#help-scroll", VerticalScroll).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def action_scroll_down(self) -> None:
        self.query_one("#help-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#help-scroll", VerticalScroll).scroll_up()
