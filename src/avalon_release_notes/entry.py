"""A changelog entry (spec section 4) and its plain-text rendering for the client manifest."""
from dataclasses import dataclass

from avalon_release_notes.gamelinks import plain, resolve
from avalon_release_notes.notes import is_bot, player_note
from avalon_release_notes.titles import Title, parse_title

_KIND_BY_TYPE = {"feat": "new", "perf": "improved", "fix": "fixed"}
_SECTIONS = [("new", "New"), ("improved", "Improved"), ("fixed", "Fixed"), ("changed", "Changed")]
_HIDDEN = ("internal", "dependencies")


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    author: str
    merged_at: str
    url: str


def kind_for(title: Title, bot: bool) -> str:
    if bot:
        return "dependencies"
    if title.type is None:
        return "changed"  # a title from before the convention (backfill)
    return _KIND_BY_TYPE.get(title.type, "internal")


def make_item(pr: PullRequest, *, public: bool, lookup=None, warn=None) -> dict:
    title = parse_title(pr.title)
    bot = is_bot(pr.author)
    # pr-check requires the note before merge; a PR from before the rollout falls back to its title.
    text = (None if bot else player_note(pr.body)) or title.summary
    if lookup is not None:
        text, warnings = resolve(text, lookup)
        for w in warnings:
            if warn:
                warn(w)
    item = {"kind": kind_for(title, bot), "text": text, "breaking": title.breaking}
    if public:
        item["pr"] = pr.number
        item["prUrl"] = pr.url
    return item


def build_entry(*, product, channel, version, build, commit, published_at, release_url, prs, public, lookup=None, warn=None) -> dict:
    ordered = sorted(prs, key=lambda p: (p.merged_at, p.number))
    return {
        "schema": 1,
        "product": product,
        "channel": channel,
        "version": version,
        "build": build,
        "commit": commit,
        "publishedAt": published_at,
        "releaseUrl": release_url if public else None,
        "items": [make_item(p, public=public, lookup=lookup, warn=warn) for p in ordered],
    }


def render_text(entry: dict) -> str:
    lines: list[str] = []
    for kind, label in _SECTIONS:
        items = [i for i in entry["items"] if i["kind"] == kind]
        if items:
            lines += [f"{label}:"] + [f"- {plain(i['text'])}{' (breaking)' if i['breaking'] else ''}" for i in items] + [""]
    hidden = sum(1 for i in entry["items"] if i["kind"] in _HIDDEN)
    if not lines:
        lines.append("No player-facing changes.")
    if hidden:
        lines.append(f"Also: {hidden} internal change{'' if hidden == 1 else 's'}")
    return "\n".join(lines).strip()
