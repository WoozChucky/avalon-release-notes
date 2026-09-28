"""avalon-release-notes: check-pr | build | render | previous | upload | publish."""
import argparse
import json
import os
import urllib.error
from pathlib import Path

from avalon_release_notes.entry import build_entry, render_text
from avalon_release_notes.github import default_fetch, prs_in_range, resolve_sha
from avalon_release_notes.notes import first_person, is_bot, player_note

HINT = (
    "The pull request description needs a line `Player note: <one sentence>`, written like a patch note: "
    "third person, starting with what changed. Examples: \"Fixed an issue where heals could raise health "
    "above the maximum.\", \"Added browser sign-in to the launcher.\", \"Increased the world server's "
    "connection limit.\" For internal work: \"No gameplay changes: faster builds.\""
)


def _check_pr(args) -> int:
    if is_bot(args.author):
        return 0
    note = player_note(os.environ.get("PR_BODY"))
    if note and first_person(note):
        print(f"::error title=Player note::Write the player note as a patch note, not in the first person. {HINT}")
        return 1
    if note:
        return 0
    print(f"::error title=Player note::{HINT}")
    return 1


def store_from_env():
    """The avalon-dist store (imported on use, so check-pr needs no boto3)."""
    from avalon_release_notes.store import from_env

    return from_env()


def _make_entry(args, previous: str | None) -> dict:
    fetch = default_fetch(os.environ.get("GITHUB_TOKEN"))
    commit = resolve_sha(fetch, args.repo, args.commit)
    prs = prs_in_range(fetch, args.repo, previous, commit)
    # A private repository cannot make the note block a merge, so a note can be missing: say which.
    missing = [f"#{p.number}" for p in prs if not is_bot(p.author) and not player_note(p.body)]
    if missing:
        print(f"::warning title=Player note::no player note, the title is shown instead: {', '.join(missing)}")
    return build_entry(product=args.product, channel=args.channel, version=args.version, build=args.build,
                       commit=commit, published_at=args.published_at, release_url=args.release_url,
                       prs=prs, public=args.public)


def _write(entry: dict, out: str | None, render_to: str | None) -> None:
    if out:
        Path(out).write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if render_to:
        Path(render_to).write_text(render_text(entry) + "\n", encoding="utf-8", newline="\n")


def _build(args) -> int:
    entry = _make_entry(args, args.previous_commit)
    # The notes file is written here, as UTF-8: piping the text through a Windows shell would re-encode it.
    _write(entry, args.out, args.render_to)
    print(f"{len(entry['items'])} change(s) -> {args.out}")
    return 0


def _previous(args) -> int:
    print((store_from_env().latest(args.product, args.channel) or {}).get("commit", ""))
    return 0


def _upload(args) -> int:
    from avalon_release_notes.store import AlreadyPublished, EntryConflict

    try:
        print(store_from_env().put(json.loads(Path(args.entry).read_text(encoding="utf-8"))))
    except AlreadyPublished as e:
        print(e)
        return 0
    except EntryConflict as e:
        print(f"::error title=Changelog::{e}")
        return 3
    return 0


def _publish(args) -> int:
    from avalon_release_notes.store import AlreadyPublished, EntryConflict, entry_key

    store = store_from_env()
    try:
        commit = resolve_sha(default_fetch(os.environ.get("GITHUB_TOKEN")), args.repo, args.commit)
        # A re-run of this release: its entry is there already, for this commit.
        existing = store.get(entry_key(args.product, args.channel, args.version, args.build))
        if existing is not None and existing.get("commit") == commit:
            print(f"{args.product} {args.version} is already published")
            return 0
        previous = (store.latest(args.product, args.channel) or {}).get("commit")
        args.commit = commit
        entry = _make_entry(args, previous)
    except (urllib.error.URLError, OSError) as e:
        print(f"::error title=Changelog::could not read the pull requests for {args.product} {args.version}: "
              f"{e}; the release itself is published, re-run the failed job")
        return 2
    _write(entry, args.out, args.render_to)
    try:
        print(store.put(entry))
    except AlreadyPublished as e:
        print(e)
    except EntryConflict as e:
        print(f"::error title=Changelog::{e}")
        return 3
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
    def entry_args(p):
        p.add_argument("--repo", required=True)
        p.add_argument("--product", required=True, choices=["server", "client", "launcher"])
        p.add_argument("--channel")
        p.add_argument("--version", required=True)
        p.add_argument("--build")
        p.add_argument("--commit", required=True)
        p.add_argument("--published-at", required=True)
        p.add_argument("--release-url")
        p.add_argument("--public", action="store_true")

    build = sub.add_parser("build", help="build a changelog entry from the PRs in a release range")
    entry_args(build)
    build.add_argument("--previous-commit")
    build.add_argument("--out", required=True)
    build.add_argument("--render-to")
    build.set_defaults(run=_build)
    render = sub.add_parser("render", help="print an entry as plain text (the client manifest's notes)")
    render.add_argument("--entry", required=True)
    render.set_defaults(run=_render)
    publish = sub.add_parser("publish", help="build the entry since the previous one in avalon-dist, and upload it")
    entry_args(publish)
    publish.add_argument("--out")
    publish.add_argument("--render-to")
    publish.set_defaults(run=_publish)
    previous = sub.add_parser("previous", help="print the commit of the newest entry in avalon-dist")
    previous.add_argument("--product", required=True, choices=["server", "client", "launcher"])
    previous.add_argument("--channel")
    previous.set_defaults(run=_previous)
    upload = sub.add_parser("upload", help="upload an entry to avalon-dist (entries are immutable)")
    upload.add_argument("--entry", required=True)
    upload.set_defaults(run=_upload)
    args = parser.parse_args(argv)
    if args.command in ("build", "publish"):
        # An entry is immutable once published, so a wrong key or a leaked link is refused up front.
        if args.product == "client" and not args.channel:
            parser.error("--channel is required for the client")
        if args.product == "launcher" and args.channel:
            parser.error("--channel is not for the launcher")
        if args.product == "server" and args.channel not in (None, "dev", "ptr"):
            parser.error("the server's --channel is dev or ptr; a release (live) has none")
        if args.public and args.product != "server":
            parser.error("--public is only for the server (the other repositories are private)")
    return args.run(args)
