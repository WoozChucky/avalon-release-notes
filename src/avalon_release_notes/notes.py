"""The `Player note:` line every pull request carries (bots excepted)."""
import re

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_NOTE = re.compile(r"^[ \t>*-]*player note:\**[ \t]*(?P<text>.*)$", re.I | re.M)


def player_note(body: str | None) -> str | None:
    match = _NOTE.search(_COMMENT.sub("", body or ""))
    if not match:
        return None
    text = match["text"].strip().strip("*").strip()
    return text or None


# Patch notes speak about the game, not the author: "Fixed an issue where…", never "I fixed…".
# Quoted text (a menu name, a quest title) is not the author speaking. "us" and "me" count only in lower
# case ("the US realm"), and a Roman numeral I after Rank/Tier/Phase, or in "I/O", is not a pronoun.
_QUOTED = re.compile(r'"[^"]*"|“[^”]*”')
_PRONOUN_I = re.compile(r"(?<![\w/])I(?:'m|'ve|'d|'ll)?(?![\w/])")
_NUMERAL_BEFORE = re.compile(r"\b(?:Rank|Tier|Phase|Act|Part|Chapter|Wave|Mark|Level)\s+$")
_OTHER = re.compile(r"\b(?:us|me)\b|\b(?i:we|we're|we've|we'll|we'd|our|ours|my)\b")


def first_person(note: str) -> bool:
    text = _QUOTED.sub(" ", note)
    if _OTHER.search(text):
        return True
    return any(not _NUMERAL_BEFORE.search(text[:m.start()]) for m in _PRONOUN_I.finditer(text))


def is_bot(login: str | None) -> bool:
    return (login or "").endswith("[bot]")
