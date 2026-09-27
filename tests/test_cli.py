import json

from avalon_release_notes import cli
from avalon_release_notes.cli import main


def test_check_pr_passes_with_a_note(monkeypatch, capsys):
    monkeypatch.setenv("PR_BODY", "Player note: Faster builds.")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0


def test_check_pr_fails_without_a_note(monkeypatch, capsys):
    monkeypatch.setenv("PR_BODY", "## What\nstuff")
    assert main(["check-pr", "--author", "WoozChucky"]) == 1
    assert "::error" in capsys.readouterr().out


def test_bots_need_no_note(monkeypatch):
    monkeypatch.setenv("PR_BODY", "")
    assert main(["check-pr", "--author", "renovate[bot]"]) == 0
import json

from avalon_release_notes import cli


def test_build_and_render(monkeypatch, tmp_path, capsys):
    from avalon_release_notes.entry import PullRequest
    monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "s" * 40)
    monkeypatch.setattr(cli, "prs_in_range", lambda fetch, repo, prev, head: [
        PullRequest(1, "feat: a", "Player note: A thing.", "WoozChucky", "2026-09-27T12:00:00Z", "https://gh/pull/1")])
    out = tmp_path / "entry.json"
    assert cli.main(["build", "--repo", "WoozChucky/Avalon.Server", "--product", "server", "--version", "0.7.0",
                     "--commit", "c" * 40, "--previous-commit", "p" * 40, "--published-at", "2026-09-27T18:00:00Z",
                     "--release-url", "https://github.com/WoozChucky/Avalon.Server/releases/tag/v0.7.0",
                     "--public", "--out", str(out)]) == 0
    entry = json.loads(out.read_text(encoding="utf-8"))
    assert entry["items"][0]["prUrl"] == "https://gh/pull/1" and entry["releaseUrl"].endswith("v0.7.0")
    assert entry["commit"] == "s" * 40  # the released commit, resolved from whatever ref was passed
    capsys.readouterr()  # drop what build printed
    assert cli.main(["render", "--entry", str(out)]) == 0
    assert capsys.readouterr().out.strip() == "New:\n- A thing."
