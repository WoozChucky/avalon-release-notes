"""avalon-release-notes: check-pr | build | render."""
import argparse
import os

from avalon_release_notes.notes import is_bot, player_note

HINT = (
    "The pull request description needs a line `Player note: <one plain sentence>` saying what a player "
    "would notice (for internal work, what it means, e.g. \"Faster builds; nothing changes in the game\")."
)


def _check_pr(args) -> int:
    if is_bot(args.author) or player_note(os.environ.get("PR_BODY")):
        return 0
    print(f"::error title=Player note::{HINT}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="avalon-release-notes")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-pr", help="the PR description (env PR_BODY) has a player note")
    check.add_argument("--author", required=True)
    check.set_defaults(run=_check_pr)
    args = parser.parse_args(argv)
    return args.run(args)
