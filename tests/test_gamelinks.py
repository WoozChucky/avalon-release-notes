import io
import json
import urllib.error

import pytest

from avalon_release_notes import gamelinks
from avalon_release_notes.gamelinks import Link, api_lookup, links, malformed, plain, resolve


def test_links_parse_every_form():
    assert links("Fixed [item:14].") == [Link("item", 14, None, None, "[item:14]")]
    assert links("[ability:210@3|Fireball]") == [Link("ability", 210, 3, "Fireball", "[ability:210@3|Fireball]")]
    assert links("[item:14|  ]")[0].name is None
    assert links("[item:14|  Helm  ]")[0].name == "Helm"
    assert links("[item:1@2]")[0].world == 2


@pytest.mark.parametrize("text", ["[Item:14]", "[item:abc]", "[item:14@x]", "[item 14]", "[item:1234567890]", "[item:]"])
def test_non_tokens_are_not_links(text):
    assert links(text) == []


def test_malformed_lists_lookalikes_that_are_not_tokens():
    assert malformed("[itme:14] [Item:2] [item:14]") == ["[itme:14]", "[Item:2]"]
    assert malformed("[note: see below] [x:y] [item 14] [a:1b]") == ["[a:1b]"]
    assert malformed("[item:abc] [item:14@x] [ABILITY:3|x] [item 14] [item:14|n]") == [
        "[item:abc]", "[item:14@x]", "[ABILITY:3|x]"]


def test_plain():
    assert plain("Fixed [item:14|Barkplate Helm] and [ability:2].") == "Fixed Barkplate Helm and ability #2."
    assert plain("nothing here") == "nothing here"
    assert plain("[Item:14] and [item 14]") == "[Item:14] and [item 14]"
    assert plain("[item:14|  ]") == "item #14"


class Fake:
    def __init__(self, names=None, error=None):
        self.calls, self.names, self.error = [], names or {}, error

    def __call__(self, kind, id, world):
        self.calls.append((kind, id, world))
        if self.error:
            raise self.error
        return self.names.get((kind, id))


def test_resolve_freezes_the_name():
    fake = Fake({("item", 14): "Barkplate Helm"})
    assert resolve("Buffed [item:14].", fake) == ("Buffed [item:14|Barkplate Helm].", [])


def test_resolve_keeps_a_resolved_token_without_lookup():
    fake = Fake()
    assert resolve("[item:14|Old]", fake) == ("[item:14|Old]", [])
    assert fake.calls == []


def test_resolve_twice_is_stable():
    fake = Fake({("item", 14): "Helm"})
    once, _ = resolve("[item:14]", fake)
    assert resolve(once, fake)[0] == once and len(fake.calls) == 1


def test_resolve_none_and_error_leave_token_and_warn():
    text, warnings = resolve("[item:14]", Fake())
    assert text == "[item:14]" and len(warnings) == 1 and "[item:14]" in warnings[0]
    text, warnings = resolve("[item:14]", Fake(error=OSError("boom")))
    assert text == "[item:14]" and len(warnings) == 1 and "boom" in warnings[0]


def test_resolve_caps_lookups():
    fake = Fake({("item", n): f"N{n}" for n in range(1, 12)})
    text, warnings = resolve(" ".join(f"[item:{n}]" for n in range(1, 12)), fake)
    assert len(fake.calls) == 10
    assert text.endswith("[item:11]") and "[item:10|N10]" in text
    assert len(warnings) == 1 and "[item:11]" in warnings[0]


def test_resolve_passes_the_world_through():
    fake = Fake({("ability", 5): "Bolt"})
    assert resolve("[ability:5@3]", fake)[0] == "[ability:5@3|Bolt]"
    assert fake.calls == [("ability", 5, 3)]


def test_resolve_sanitizes_names():
    assert resolve("[item:1]", Fake({("item", 1): "A]\nB"}))[0] == "[item:1|A B]"


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener(routes, seen):
    def urlopen(request, timeout=None):
        seen.append((request.full_url, timeout, request.get_header("Accept")))
        path = request.full_url.removeprefix("http://api")
        value = routes[path]
        if isinstance(value, int):
            raise urllib.error.HTTPError(request.full_url, value, "err", {}, None)
        return Resp(json.dumps(value).encode())
    return urlopen


def test_api_lookup(monkeypatch):
    seen = []
    monkeypatch.setattr(gamelinks.urllib.request, "urlopen", opener({
        "/public/world": {"defaultWorldId": 2, "worlds": []},
        "/public/world/2/item/14": {"name": "Barkplate Helm"},
        "/public/world/2/item/15": 404,
        "/public/world/3/ability/5": {"name": "Bolt"},
        "/public/world/2/item/16": 500,
    }, seen))
    look = api_lookup("http://api/")
    assert look("item", 14, None) == "Barkplate Helm"
    assert look("item", 15, None) is None
    assert look("ability", 5, 3) == "Bolt"
    with pytest.raises(urllib.error.HTTPError):
        look("item", 16, None)
    assert sum(1 for u, *_ in seen if u.endswith("/public/world")) == 1  # cached
    assert all(t == 5.0 and a == "application/json" for _, t, a in seen)


def test_api_lookup_without_default_world(monkeypatch):
    monkeypatch.setattr(gamelinks.urllib.request, "urlopen", opener({"/public/world": {"defaultWorldId": None, "worlds": []}}, []))
    with pytest.raises(LookupError, match="no public world"):
        api_lookup("http://api")("item", 1, None)


def test_api_lookup_is_lazy(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network")
    monkeypatch.setattr(gamelinks.urllib.request, "urlopen", boom)
    api_lookup("http://api")
