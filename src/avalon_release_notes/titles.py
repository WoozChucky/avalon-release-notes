"""Pull request titles in Conventional Commits form: type(scope)!: summary (#123)."""
import re
from dataclasses import dataclass

TYPES = ("feat", "fix", "docs", "chore", "refactor", "test", "ci", "perf", "build", "style", "revert")
_TITLE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9-]+(?:,[a-z0-9-]+)*)\))?(?P<breaking>!)?: "
    r"(?P<summary>\S.*?)(?: \(#\d+(?:, #\d+)*\))?$"
)


@dataclass(frozen=True)
class Title:
    type: str | None
    scope: str | None
    breaking: bool
    summary: str


def parse_title(title: str) -> Title:
    text = title.strip()
    match = _TITLE.match(text)
    if not match or match["type"] not in TYPES:
        return Title(None, None, False, text)
    return Title(match["type"], match["scope"], bool(match["breaking"]), match["summary"])
