"""The pull requests merged into main between two released commits (GitHub REST API)."""
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from avalon_release_notes.entry import PullRequest

Fetch = Callable[[str], Any]
PAGE = 100


def default_fetch(token: str | None) -> Fetch:
    def fetch(path: str) -> Any:
        request = urllib.request.Request("https://api.github.com" + path, headers={
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            # Rate limited: wait as told (at most a minute) and try once more; anything else is final.
            if e.code not in (403, 429) or "Retry-After" not in (e.headers or {}):
                raise
            time.sleep(min(int(e.headers["Retry-After"]), 60))
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    return fetch


def _commits(fetch: Fetch, repo: str, base: str, head: str) -> list[str]:
    shas: list[str] = []
    page = 1
    while True:
        commits = fetch(f"/repos/{repo}/compare/{base}...{head}?per_page={PAGE}&page={page}")["commits"]
        shas += [c["sha"] for c in commits]
        if len(commits) < PAGE:
            return shas
        page += 1


def resolve_sha(fetch: Fetch, repo: str, ref: str) -> str:
    """A tag, branch or short sha as the full commit sha: the next release's range starts from it."""
    return fetch(f"/repos/{repo}/commits/{ref}")["sha"]


def prs_in_range(fetch: Fetch, repo: str, previous: str | None, head: str) -> list[PullRequest]:
    shas = [head] if previous is None else _commits(fetch, repo, previous, head)
    found: dict[int, PullRequest] = {}
    for sha in shas:
        for p in fetch(f"/repos/{repo}/commits/{sha}/pulls"):
            if p.get("merged_at") and p["base"]["ref"] == "main":
                found.setdefault(p["number"], PullRequest(
                    p["number"], p["title"], p.get("body"), p["user"]["login"], p["merged_at"], p["html_url"]))
    return sorted(found.values(), key=lambda pr: (pr.merged_at, pr.number))
