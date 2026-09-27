from urllib.parse import parse_qs, urlsplit

from avalon_release_notes.github import prs_in_range


def pull(n, base="main", merged="2026-09-27T12:00:00Z"):
    return {"number": n, "title": f"fix: {n}", "body": f"Player note: {n}", "user": {"login": "WoozChucky"},
            "merged_at": merged, "html_url": f"https://gh/pull/{n}", "base": {"ref": base}}


class FakeGitHub:
    def __init__(self, compare_pages, pulls_by_sha):
        self.compare_pages, self.pulls_by_sha, self.calls = compare_pages, pulls_by_sha, []

    def __call__(self, path):
        self.calls.append(path)
        if "/compare/" in path:
            page = int(parse_qs(urlsplit(path).query)["page"][0])
            return {"commits": [{"sha": s} for s in self.compare_pages[page - 1]]}
        sha = path.split("/commits/")[1].split("/pulls")[0]
        return self.pulls_by_sha.get(sha, [])


def test_the_first_release_takes_only_its_own_pr():
    fake = FakeGitHub([], {"h": [pull(7)]})
    assert [p.number for p in prs_in_range(fake, "o/r", None, "h")] == [7]
    assert not any("/compare/" in c for c in fake.calls)


def test_dedupes_and_keeps_main_only():
    fake = FakeGitHub([["a", "b", "c"]], {
        "a": [pull(1, merged="2026-09-27T12:00:02Z")],
        "b": [pull(1, merged="2026-09-27T12:00:02Z"), pull(2, merged="2026-09-27T12:00:01Z")],
        "c": [pull(3, base="release/x"), {**pull(4), "merged_at": None}],
    })
    assert [p.number for p in prs_in_range(fake, "o/r", "p", "h")] == [2, 1]


def test_pages_through_a_long_range():
    first = [f"s{i}" for i in range(100)]
    fake = FakeGitHub([first, ["last"]], {"last": [pull(9)], "s0": [pull(8)]})
    assert [p.number for p in prs_in_range(fake, "o/r", "p", "h")] == [8, 9]
    assert any("page=2" in c for c in fake.calls)


def test_maps_the_api_fields():
    fake = FakeGitHub([], {"h": [pull(5)]})
    (pr,) = prs_in_range(fake, "o/r", None, "h")
    assert (pr.title, pr.body, pr.author, pr.url) == ("fix: 5", "Player note: 5", "WoozChucky", "https://gh/pull/5")


def test_resolves_a_ref_to_its_full_sha():
    from avalon_release_notes.github import resolve_sha
    calls = []

    def fetch(path):
        calls.append(path)
        return {"sha": "f" * 40}

    assert resolve_sha(fetch, "o/r", "v0.6.0") == "f" * 40
    assert calls == ["/repos/o/r/commits/v0.6.0"]


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def test_default_fetch_sends_the_token_and_a_timeout(monkeypatch):
    import urllib.request
    from avalon_release_notes.github import default_fetch
    seen = {}

    def urlopen(request, timeout):
        seen["auth"], seen["timeout"], seen["url"] = request.get_header("Authorization"), timeout, request.full_url
        return _Response(b'{"sha": "x"}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert default_fetch("t0ken")("/repos/o/r/commits/main") == {"sha": "x"}
    assert seen == {"auth": "Bearer t0ken", "timeout": 30, "url": "https://api.github.com/repos/o/r/commits/main"}


def test_default_fetch_waits_once_when_rate_limited(monkeypatch):
    import urllib.error
    import urllib.request
    from avalon_release_notes import github
    calls, slept = [], []

    def urlopen(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, "slow down", {"Retry-After": "7"}, None)
        return _Response(b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(github.time, "sleep", slept.append)
    assert github.default_fetch(None)("/x") == []
    assert slept == [7] and len(calls) == 2
