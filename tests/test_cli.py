import json

import pytest

from avalon_release_notes import cli
from avalon_release_notes.cli import main


def test_check_pr_passes_with_a_note(monkeypatch, capsys):
    monkeypatch.setenv("PR_BODY", "Player note: Faster builds.")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0


def test_check_pr_fails_without_a_note(monkeypatch, capsys):
    monkeypatch.setenv("PR_BODY", "## What\nstuff")
    assert main(["check-pr", "--author", "WoozChucky"]) == 1
    assert "::error" in capsys.readouterr().out


def test_check_pr_refuses_a_first_person_note(monkeypatch, capsys):
    monkeypatch.setenv("PR_BODY", "Player note: I fixed the heals.")
    assert main(["check-pr", "--author", "WoozChucky"]) == 1
    assert "patch note" in capsys.readouterr().out.lower()


def test_bots_need_no_note(monkeypatch):
    monkeypatch.setenv("PR_BODY", "")
    assert main(["check-pr", "--author", "renovate[bot]"]) == 0
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


def _build_args(*extra):
    return ["build", "--repo", "o/r", "--version", "0.1.0", "--commit", "c" * 40,
            "--published-at", "2026-09-27T18:00:00Z", "--out", "unused.json", *extra]


def test_build_refuses_flags_that_do_not_fit_the_product(capsys):
    for extra in (["--product", "client"],                                  # a client entry needs its channel
                  ["--product", "launcher", "--channel", "dev"],             # launcher doesn't have channels
                  ["--product", "launcher", "--public"],                     # only the server is public
                  ["--product", "client", "--channel", "ptr", "--public"]):
        with pytest.raises(SystemExit) as exit_:
            cli.main(_build_args(*extra))
        assert exit_.value.code == 2, extra


def test_build_names_the_prs_that_fell_back_to_their_title(monkeypatch, tmp_path, capsys):
    from avalon_release_notes.entry import PullRequest
    monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "s" * 40)
    monkeypatch.setattr(cli, "prs_in_range", lambda fetch, repo, prev, head: [
        PullRequest(3, "fix: a", "no note", "WoozChucky", "2026-09-27T12:00:00Z", "u3"),
        PullRequest(4, "fix: b", "Player note: B.", "WoozChucky", "2026-09-27T12:00:01Z", "u4"),
        PullRequest(5, "chore(deps): c", "", "renovate[bot]", "2026-09-27T12:00:02Z", "u5")])
    assert cli.main(["build", "--repo", "o/r", "--product", "launcher", "--version", "0.1.0", "--commit", "h",
                     "--published-at", "t", "--out", str(tmp_path / "e.json")]) == 0
    out = capsys.readouterr().out
    assert "#3" in out and "#4" not in out and "#5" not in out


def _seeded_store(entries):
    import boto3
    from moto import mock_aws

    from avalon_release_notes.store import Store
    mock = mock_aws()
    mock.start()
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="avalon-dist")
    store = Store(s3, "avalon-dist")
    for e in entries:
        store.put(e)
    return store, mock


def _entry(**over):
    e = {"schema": 1, "product": "server", "channel": None, "version": "0.6.0", "build": None, "commit": "p" * 40,
         "publishedAt": "2026-09-27T14:00:00Z", "releaseUrl": None, "items": []}
    e.update(over)
    return e


def test_previous_prints_the_newest_commit(monkeypatch, capsys):
    store, mock = _seeded_store([_entry()])
    try:
        monkeypatch.setattr(cli, "store_from_env", lambda: store)
        assert cli.main(["previous", "--product", "server"]) == 0
        assert capsys.readouterr().out.strip() == "p" * 40
        assert cli.main(["previous", "--product", "launcher"]) == 0
        assert capsys.readouterr().out.strip() == ""
    finally:
        mock.stop()


def test_upload_refuses_a_different_entry(monkeypatch, tmp_path, capsys):
    store, mock = _seeded_store([_entry()])
    try:
        monkeypatch.setattr(cli, "store_from_env", lambda: store)
        f = tmp_path / "e.json"
        # Another commit under the same key: a real conflict (the same commit would be a re-run).
        f.write_text(json.dumps(_entry(commit="q" * 40)), encoding="utf-8")
        assert cli.main(["upload", "--entry", str(f)]) == 3
        assert "::error" in capsys.readouterr().out
    finally:
        mock.stop()


def test_publish_uses_the_previous_entry_and_uploads(monkeypatch, tmp_path, capsys):
    from avalon_release_notes.entry import PullRequest
    store, mock = _seeded_store([_entry()])
    try:
        monkeypatch.setattr(cli, "store_from_env", lambda: store)
        monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "h" * 40)
        seen = {}

        def prs(fetch, repo, prev, head):
            seen["prev"] = prev
            return [PullRequest(9, "fix: a", "Player note: Fixed a thing.", "WoozChucky", "2026-09-28T12:00:00Z", "u")]

        monkeypatch.setattr(cli, "prs_in_range", prs)
        notes = tmp_path / "notes.txt"
        assert cli.main(["publish", "--repo", "WoozChucky/Avalon.Server", "--product", "server", "--version", "0.7.0",
                         "--commit", "v0.7.0", "--published-at", "2026-09-28T13:00:00Z", "--public",
                         "--render-to", str(notes)]) == 0
        assert seen["prev"] == "p" * 40
        assert store.latest("server", None)["version"] == "0.7.0"
        assert notes.read_text(encoding="utf-8").strip() == "Fixed:\n- Fixed a thing."
    finally:
        mock.stop()


def test_publish_reports_github_errors_plainly(monkeypatch, capsys):
    import urllib.error
    store, mock = _seeded_store([])
    try:
        monkeypatch.setattr(cli, "store_from_env", lambda: store)

        def refused(fetch, repo, ref):
            raise urllib.error.HTTPError("https://api.github.com/x", 403, "rate limited", {}, None)

        monkeypatch.setattr(cli, "resolve_sha", refused)
        assert cli.main(["publish", "--repo", "o/r", "--product", "launcher", "--version", "0.1.2",
                         "--commit", "h", "--published-at", "t"]) == 2
        out = capsys.readouterr().out
        assert "::error" in out and "launcher 0.1.2" in out
    finally:
        mock.stop()



def test_publish_twice_for_the_same_commit_says_already_published(monkeypatch, capsys):
    from avalon_release_notes.entry import PullRequest
    store, mock = _seeded_store([_entry()])
    try:
        monkeypatch.setattr(cli, "store_from_env", lambda: store)
        monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "h" * 40)
        monkeypatch.setattr(cli, "prs_in_range", lambda fetch, repo, prev, head: [
            PullRequest(9, "fix: a", "Player note: Fixed a thing.", "WoozChucky", "2026-09-28T12:00:00Z", "u")])
        args = ["publish", "--repo", "o/r", "--product", "server", "--version", "0.7.0", "--commit", "v0.7.0",
                "--published-at", "2026-09-28T13:00:00Z", "--public"]
        assert cli.main(args) == 0
        args[-2] = "2026-09-28T14:00:00Z"  # a re-run later: another time, same release
        assert cli.main(args) == 0
        assert "already published" in capsys.readouterr().out
        assert store.latest("server", None)["publishedAt"] == "2026-09-28T13:00:00Z"
    finally:
        mock.stop()


def test_upload_of_a_rebuilt_entry_for_the_same_commit_is_already_published(monkeypatch, tmp_path, capsys):
    store, mock = _seeded_store([_entry()])
    try:
        monkeypatch.setattr(cli, "store_from_env", lambda: store)
        f = tmp_path / "e.json"
        f.write_text(json.dumps(_entry(publishedAt="2026-09-28T00:00:00Z")), encoding="utf-8")
        assert cli.main(["upload", "--entry", str(f)]) == 0
        assert "already published" in capsys.readouterr().out
    finally:
        mock.stop()


def test_build_writes_the_rendered_notes_as_utf8(monkeypatch, tmp_path):
    from avalon_release_notes.entry import PullRequest
    monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "s" * 40)
    monkeypatch.setattr(cli, "prs_in_range", lambda fetch, repo, prev, head: [
        PullRequest(1, "fix: a", "Player note: Fixed the café sign — it’s readable now.", "WoozChucky",
                    "2026-09-27T12:00:00Z", "u")])
    notes = tmp_path / "notes.md"
    assert cli.main(["build", "--repo", "o/r", "--product", "launcher", "--version", "0.1.0", "--commit", "h",
                     "--published-at", "t", "--out", str(tmp_path / "e.json"), "--render-to", str(notes)]) == 0
    assert notes.read_bytes().decode("utf-8") == "Fixed:\n- Fixed the café sign — it’s readable now.\n"


@pytest.mark.parametrize("product,channel", [("server", "live"), ("server", "beta"), ("launcher", "dev")])
def test_channels_that_do_not_fit_the_product_are_refused(product, channel, capsys):
    with pytest.raises(SystemExit) as e:
        main(["build", "--repo", "WoozChucky/Avalon.Server", "--product", product, "--channel", channel,
              "--version", "0.7.1", "--commit", "c" * 40, "--published-at", "2026-09-28T02:00:00Z", "--out", "x.json"])
    assert e.value.code == 2


def test_server_dev_build_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "s" * 40)
    monkeypatch.setattr(cli, "prs_in_range", lambda fetch, repo, prev, head: [])
    out = tmp_path / "entry.json"
    assert main(["build", "--repo", "WoozChucky/Avalon.Server", "--product", "server", "--channel", "dev",
                 "--version", "0.7.1-dev.412", "--commit", "c" * 40, "--published-at", "2026-09-28T02:00:00Z",
                 "--public", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["channel"] == "dev"


def _check(monkeypatch, body, lookup=None):
    calls = []

    def fake(kind, id, world):
        calls.append((kind, id, world))
        if isinstance(lookup, Exception):
            raise lookup
        return lookup(kind, id, world) if lookup else None

    fake.default_world = lambda: 2
    monkeypatch.setenv("PR_BODY", body)
    monkeypatch.setattr(cli, "api_lookup", lambda base, timeout=5.0: fake)
    return calls


def test_check_pr_errors_on_a_malformed_game_link(monkeypatch, capsys):
    calls = _check(monkeypatch, "Player note: Fixed [Item:14].")
    assert main(["check-pr", "--author", "WoozChucky"]) == 1
    assert ('::error title=Player note::Malformed game link "[Item:14]". '
            'Use [item:ID] or [ability:ID], optionally [item:ID@WORLD].') in capsys.readouterr().out
    assert calls == []


def test_check_pr_warns_on_a_missing_item(monkeypatch, capsys):
    _check(monkeypatch, "Player note: Fixed [item:14].")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert "::warning title=Player note::item 14 is not on world 2 (fine if this PR adds it)." in capsys.readouterr().out


def test_check_pr_names_the_world_in_the_warning(monkeypatch, capsys):
    _check(monkeypatch, "Player note: Fixed [item:14@2].")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert "::warning title=Player note::item 14 is not on world 2 (fine if this PR adds it)." in capsys.readouterr().out


def test_check_pr_prints_the_found_name(monkeypatch, capsys):
    _check(monkeypatch, "Player note: Fixed [item:14].", lambda k, i, w: "Barkplate Helm")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert "item:14 → Barkplate Helm" in capsys.readouterr().out


def test_check_pr_only_notices_a_lookup_error(monkeypatch, capsys):
    _check(monkeypatch, "Player note: Fixed [item:14].", OSError("timed out"))
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert "::notice title=Player note::Could not verify game links: timed out" in capsys.readouterr().out


def test_check_pr_without_tokens_makes_no_lookups(monkeypatch, capsys):
    calls = _check(monkeypatch, "Player note: Faster builds [item 14].")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert calls == [] and capsys.readouterr().out == ""


def test_check_pr_caps_lookups_with_a_notice(monkeypatch, capsys):
    calls = _check(monkeypatch, "Player note: Fixed " + " ".join(f"[item:{n}]" for n in range(1, 13)) + ".",
                   lambda k, i, w: "N")
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert len(calls) == 10
    assert "::notice title=Player note::Could not verify game links: 2 more" in capsys.readouterr().out


def test_check_pr_uses_the_api_url_env(monkeypatch):
    seen = []
    monkeypatch.setenv("PR_BODY", "Player note: Fixed [item:14].")
    monkeypatch.setenv("AVALON_API_URL", "http://x/api")
    monkeypatch.setattr(cli, "api_lookup", lambda base, timeout=5.0: seen.append(base) or (lambda k, i, w: "N"))
    assert main(["check-pr", "--author", "WoozChucky"]) == 0
    assert seen == ["http://x/api"]


def test_build_freezes_names_and_warns(monkeypatch, tmp_path, capsys):
    from avalon_release_notes.entry import PullRequest
    monkeypatch.setattr(cli, "resolve_sha", lambda fetch, repo, ref: "s" * 40)
    monkeypatch.setattr(cli, "prs_in_range", lambda fetch, repo, prev, head: [
        PullRequest(1, "feat: a", "Player note: Added [item:14] and [item:15].", "WoozChucky",
                    "2026-09-27T12:00:00Z", "https://gh/pull/1")])
    monkeypatch.setattr(cli, "api_lookup", lambda base, timeout=5.0: lambda k, i, w: "Helm" if i == 14 else None)
    out = tmp_path / "entry.json"
    assert cli.main(_build_args("--product", "server", "--out", str(out))) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["items"][0]["text"] == "Added [item:14|Helm] and [item:15]."
    assert "::warning title=Changelog::" in capsys.readouterr().out
