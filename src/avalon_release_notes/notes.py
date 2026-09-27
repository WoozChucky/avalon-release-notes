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
# "us" and "me" only in lower case, so "the US realm" is not first person.
_FIRST_PERSON = re.compile(r"\b(?:I|I'm|I've|I'd|I'll|us|me)\b|\b(?i:we|we're|we've|we'll|we'd|our|ours|my|mine)\b")


def first_person(note: str) -> bool:
    return bool(_FIRST_PERSON.search(note))


def is_bot(login: str | None) -> bool:
    return (login or "").endswith("[bot]")
