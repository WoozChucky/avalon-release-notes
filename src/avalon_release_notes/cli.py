"""avalon-release-notes: check-pr | build | render."""
import argparse
import json
import os
from pathlib import Path

from avalon_release_notes.entry import build_entry, render_text
from avalon_release_notes.github import default_fetch, prs_in_range, resolve_sha
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


def _build(args) -> int:
    fetch = default_fetch(os.environ.get("GITHUB_TOKEN"))
    commit = resolve_sha(fetch, args.repo, args.commit)
    prs = prs_in_range(fetch, args.repo, args.previous_commit, commit)
    entry = build_entry(product=args.product, channel=args.channel, version=args.version, build=args.build,
                        commit=commit, published_at=args.published_at, release_url=args.release_url,
                        prs=prs, public=args.public)
    Path(args.out).write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entry['items'])} change(s) -> {args.out}")
    return 0


def _render(args) -> int:
    print(render_text(json.loads(Path(args.entry).read_text(encoding="utf-8"))))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="avalon-release-notes")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-pr", help="the PR description (env PR_BODY) has a player note")
    check.add_argument("--author", required=True)
    check.set_defaults(run=_check_pr)
    build = sub.add_parser("build", help="build a changelog entry from the PRs in a release range")
    build.add_argument("--repo", required=True)
    build.add_argument("--product", required=True, choices=["server", "client", "launcher"])
    build.add_argument("--channel")
    build.add_argument("--version", required=True)
    build.add_argument("--build")
    build.add_argument("--commit", required=True)
    build.add_argument("--previous-commit")
    build.add_argument("--published-at", required=True)
    build.add_argument("--release-url")
    build.add_argument("--public", action="store_true")
    build.add_argument("--out", required=True)
    build.set_defaults(run=_build)
    render = sub.add_parser("render", help="print an entry as plain text (the client manifest's notes)")
    render.add_argument("--entry", required=True)
    render.set_defaults(run=_render)
    args = parser.parse_args(argv)
    return args.run(args)
