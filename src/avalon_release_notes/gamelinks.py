"""Item and ability links in player notes: [item:14], [ability:210@3|Fireball] (see README, "Game links")."""
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

DEFAULT_API = "https://avalon.nunolevezinho.xyz/api"
TOKEN = re.compile(r"\[(item|ability):(\d{1,9})(?:@(\d{1,9}))?(?:\|([^\]\n]+))?\]")
KIND_LOOKALIKE = re.compile(r"\[(?:item|ability):[^\]\n]*\]", re.IGNORECASE)  # a known kind, anything after
LOOKALIKE = re.compile(r"\[[A-Za-z]+:\d[^\]\n]*\]")  # any word, then a digit: catches misspelt kinds

# (kind, id, world) -> name, None when the API says 404; raises on any other failure.
Lookup = Callable[[str, int, int | None], str | None]


@dataclass(frozen=True)
class Link:
    kind: str
    id: int
    world: int | None
    name: str | None
    raw: str


def _link(m: re.Match) -> Link:
    name = (m.group(4) or "").strip() or None
    return Link(m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None, name, m.group(0))


def links(text: str) -> list[Link]:
    return [_link(m) for m in TOKEN.finditer(text)]


def malformed(text: str) -> list[str]:
    """Look-alikes (either pattern, deduplicated, in order) that aren't tokens, as written."""
    found = {m.span(): m.group(0) for p in (KIND_LOOKALIKE, LOOKALIKE) for m in p.finditer(text)}
    return [raw for _, raw in sorted(found.items()) if not TOKEN.fullmatch(raw)]


def plain(text: str) -> str:
    def name(m: re.Match) -> str:
        link = _link(m)
        return link.name or f"{link.kind} #{link.id}"
    return TOKEN.sub(name, text)


def _clean(name: str) -> str:
    return " ".join(name.replace("]", " ").replace("|", " ").split())


def resolve(text: str, lookup: Lookup, limit: int = 10) -> tuple[str, list[str]]:
    """Freeze names into the tokens. A token that cannot be resolved stays as it is, with a warning."""
    warnings: list[str] = []
    cache: dict[tuple, str | None] = {}
    looked_up = 0

    def sub(m: re.Match) -> str:
        nonlocal looked_up
        link = _link(m)
        if link.name:
            return link.raw
        key = (link.kind, link.id, link.world)
        if key not in cache:
            if looked_up >= limit:
                warnings.append(f"{link.raw} was not looked up (at most {limit} lookups per note)")
                return link.raw
            looked_up += 1
            try:
                cache[key] = lookup(*key)
            except Exception as e:  # noqa: BLE001 - any failure leaves the token as written
                warnings.append(f"could not look up {link.raw}: {e}")
                return link.raw
        name = _clean(cache[key] or "")
        if not name:
            warnings.append(f"{link.raw} was not found")
            return link.raw
        world = f"@{link.world}" if link.world is not None else ""
        return f"[{link.kind}:{link.id}{world}|{name}]"

    return TOKEN.sub(sub, text), warnings


def api_lookup(base: str, timeout: float = 5.0) -> Lookup:
    """Look names up in the public API. Nothing is requested until the first lookup."""
    base = base.rstrip("/")
    default_world: list[int] = []

    def get(path: str):
        request = urllib.request.Request(base + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def world_id() -> int:
        if not default_world:
            world = get("/public/world").get("defaultWorldId")
            if world is None:
                raise LookupError("no public world")
            default_world.append(int(world))
        return default_world[0]

    def lookup(kind: str, id: int, world: int | None) -> str | None:
        w = world if world is not None else world_id()
        try:
            return get(f"/public/world/{w}/{kind}/{id}")["name"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    lookup.default_world = lambda: default_world[0] if default_world else None  # type: ignore[attr-defined]
    return lookup
