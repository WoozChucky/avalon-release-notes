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
