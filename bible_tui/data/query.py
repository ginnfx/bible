"""Turn what a person types into an FTS5 MATCH expression.

The previous implementation quoted every token, which made punctuation safe
but silently disabled every FTS5 operator - no phrases, no booleans, no
wildcards. This parses a small, forgiving query language instead and emits
the operators deliberately:

===========================  ==========================================
``love one another``         all three words, in any order
``"love one another"``       that exact phrase
``love OR charity``          either word
``love NOT world``           the first without the second
``love -world``              the same thing, shorter
``lov*``                     any word starting with "lov"
``love NEAR/5 world``        both words within five words of each other
``(love OR charity) god``    grouping
===========================  ==========================================

Every literal is quoted on the way out, so apostrophes, hyphens and stray
punctuation can't break the expression or inject syntax. Operators are only
recognised in UPPERCASE, so searching for the word "not" still works.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Words treated as operators, and only when typed in caps - lowercase "or"
#: and "not" appear all over scripture and must stay searchable.
_BOOLEAN = {"AND", "OR", "NOT"}

#: ``NEAR/5``; a bare ``NEAR`` means the FTS5 default of 10.
_NEAR = re.compile(r"^NEAR(?:/(\d+))?$")

_DEFAULT_NEAR = 10

_TOKEN = re.compile(
    r"""
    (?P<phrase>"[^"]*"?)        # "quoted phrase", tolerating a missing close
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<minus>-(?=\S))          # -word, the NOT shorthand
  | (?P<word>[^\s()"]+)
    """,
    re.VERBOSE,
)

#: Characters FTS5 tokenizes away anyway. Stripping them keeps a term like
#: ``God's`` or ``love-feast`` from becoming an empty quoted string.
_STRIPPABLE = "'’.,;:!?"


@dataclass(frozen=True)
class ParsedQuery:
    """The FTS5 expression plus the bare words a caller may want to reuse."""

    expression: str
    #: Literal words in the query, in order, with no operators or wildcards.
    #: Used to highlight matches and to drive the typo-tolerant retry.
    terms: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.expression)


def parse(raw: str) -> ParsedQuery:
    """Build an FTS5 expression from a user's query.

    Never raises: unbalanced quotes and parentheses are repaired rather than
    rejected, because a search box that errors half-way through a word you're
    still typing is useless.
    """
    tokens = _tokenize(raw)
    if not tokens:
        return ParsedQuery("", ())

    out: list[str] = []
    terms: list[str] = []
    depth = 0
    negate_next = False
    pending_near: int | None = None

    for kind, value in tokens:
        if kind == "boolean":
            # A leading or doubled operator has nothing to join; drop it.
            if out and not _ends_with_operator(out):
                out.append(value)
            continue

        if kind == "near":
            if out and not _ends_with_operator(out):
                pending_near = int(value)
            continue

        if kind == "lparen":
            if _needs_implicit_and(out):
                out.append("AND")
            out.append("(")
            depth += 1
            continue

        if kind == "rparen":
            if depth == 0 or _ends_with_operator(out) or out[-1] == "(":
                continue  # stray or empty group
            out.append(")")
            depth -= 1
            continue

        if kind == "minus":
            negate_next = True
            continue

        # An operand: a phrase or a (possibly wildcarded) word.
        literal, wildcard, words = _operand(value, kind)
        if not literal:
            continue
        terms.extend(words)
        rendered = f'"{literal}"' + ("*" if wildcard else "")

        if pending_near is not None and out and not _ends_with_operator(out):
            out.append(_extend_near(out.pop(), rendered, pending_near))
            pending_near = None
            negate_next = False
            continue

        if negate_next:
            # FTS5's NOT is binary - it subtracts from something on the left.
            # With nothing there, "-world" has nothing to exclude from, so
            # the operand is dropped rather than emitting invalid syntax.
            negate_next = False
            if not out or _ends_with_operator(out):
                continue
            out.append("NOT")
        elif _needs_implicit_and(out):
            out.append("AND")
        out.append(rendered)

    # Repair whatever the user hadn't finished typing.
    while out and _ends_with_operator(out):
        out.pop()
    while out and out[-1] == "(":
        out.pop()
        depth -= 1
    out.extend(")" * max(depth, 0))

    return ParsedQuery(" ".join(out).strip(), tuple(terms))


def with_prefix_matching(query: ParsedQuery) -> ParsedQuery:
    """The same query with every bare word turned into a prefix match.

    Used as the first retry when a search finds nothing: most "no results"
    are a half-typed or slightly-long word, and ``believ*`` rescues those
    without any spelling analysis.
    """
    if not query.expression:
        return query
    expression = re.sub(r'("(?:[^"]*)")(?!\*)', r"\1*", query.expression)
    return ParsedQuery(expression, query.terms)


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _tokenize(raw: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for match in _TOKEN.finditer(raw or ""):
        kind = match.lastgroup
        value = match.group()
        if kind == "word":
            if value in _BOOLEAN:
                tokens.append(("boolean", value))
                continue
            near = _NEAR.match(value)
            if near:
                tokens.append(("near", near.group(1) or str(_DEFAULT_NEAR)))
                continue
        tokens.append((kind, value))
    return tokens


def _operand(value: str, kind: str) -> tuple[str, bool, list[str]]:
    """Normalise one operand into (literal, is_prefix, contained words)."""
    if kind == "phrase":
        literal = value.strip('"').strip()
        cleaned = " ".join(_clean(w) for w in literal.split())
        words = [w for w in cleaned.split() if w]
        return " ".join(words), False, words

    wildcard = value.endswith("*")
    literal = _clean(value.rstrip("*"))
    return literal, wildcard, [literal] if literal else []


def _clean(word: str) -> str:
    """Drop the punctuation FTS5 would discard, and the quote character,
    which would otherwise terminate the string we're building."""
    return word.strip(_STRIPPABLE).replace('"', "")


_NEAR_GROUP = re.compile(r"^NEAR\((?P<terms>.+), (?P<distance>\d+)\)$")


def _extend_near(left: str, right: str, distance: int) -> str:
    """Build ``NEAR(a b, n)``, folding a chained NEAR into one group.

    FTS5 takes any number of terms in a single NEAR but will not accept a
    NEAR nested inside another, so ``a NEAR/3 b NEAR/5 c`` becomes
    ``NEAR(a b c, 3)`` - the tightest distance the user asked for wins.
    """
    group = _NEAR_GROUP.match(left)
    if group:
        return f"NEAR({group['terms']} {right}, {min(distance, int(group['distance']))})"
    return f"NEAR({left} {right}, {distance})"


def _ends_with_operator(out: list[str]) -> bool:
    return bool(out) and out[-1] in {"AND", "OR", "NOT", "("}


def _needs_implicit_and(out: list[str]) -> bool:
    """Two operands side by side mean AND, the way every search box works."""
    return bool(out) and not _ends_with_operator(out)
