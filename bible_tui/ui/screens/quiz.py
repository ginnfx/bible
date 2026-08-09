"""Quiz mode - fill in the blank, one random verse at a time."""

from __future__ import annotations

import random

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from ...data.repository import BibleRepository
from ...services.reading_mode_service import generate_quiz

#: How long the verdict stays up before the next verse is drawn - long
#: enough to read "Not quite - it was..." before it's replaced.
_NEXT_VERSE_DELAY = 1.6

#: A random draw can land on a verse too short to blank (e.g. "Jesus wept.")
#: a few times in a row; give up rather than loop forever.
_MAX_DRAW_ATTEMPTS = 20


class QuizScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Done"), Binding("ctrl+n", "next", "Skip")]

    DEFAULT_CSS = """
    QuizScreen {
        align: center middle;
        background: $background 60%;
    }
    QuizScreen #box {
        width: 72;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    QuizScreen #prompt {
        margin: 1 0;
    }
    QuizScreen #result {
        margin-top: 1;
    }
    """

    def __init__(self, repo: BibleRepository, translation_code: str) -> None:
        super().__init__()
        self.repo = repo
        self.translation_code = translation_code
        self._answer = ""
        self._correct = 0
        self._asked = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(
                "[b]Quiz[/]  [$text-disabled]enter to check · ctrl+n skip · esc done[/]"
            )
            yield Static("", id="prompt")
            yield Input(placeholder="Your answer…", id="quiz-input")
            yield Static("", id="result")

    def on_mount(self) -> None:
        self._next_verse()
        self.query_one(Input).focus()

    def _next_verse(self) -> None:
        prompt = self.query_one("#prompt", Static)
        for _ in range(_MAX_DRAW_ATTEMPTS):
            verse_id = self.repo.random_verse_id(self.translation_code)
            verse = self.repo.get_verse_by_id(verse_id) if verse_id else None
            if verse is None:
                continue
            question = generate_quiz(verse.text, seed=random.randrange(1 << 30))
            if question is None:
                continue
            self._answer = question.answer
            prompt.update(f"{question.prompt}\n[$text-disabled]{verse.reference}[/]")
            self.query_one("#result", Static).update("")
            self.query_one(Input).value = ""
            return
        self._answer = ""
        prompt.update("Couldn't find a verse to quiz on right now.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not self._answer:
            return
        self._asked += 1
        correct = event.value.strip().lower() == self._answer.lower()
        if correct:
            self._correct += 1
        verdict = (
            "[$success]Correct![/]" if correct else f"[$error]Not quite[/] - it was {self._answer}"
        )
        self.query_one("#result", Static).update(
            f"{verdict}   [$text-disabled]{self._correct}/{self._asked}[/]"
        )
        self.set_timer(_NEXT_VERSE_DELAY, self._next_verse)

    def action_next(self) -> None:
        self._next_verse()

    def action_close(self) -> None:
        self.dismiss(None)
