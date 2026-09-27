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


def is_bot(login: str | None) -> bool:
    return (login or "").endswith("[bot]")
