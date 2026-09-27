# avalon-release-notes

The pull request conventions every Avalon repository follows, and the tool that turns merged pull requests into the public changelog.

## The conventions

**Title:** Conventional Commits, `type(scope)!: summary (#123)`.
- **type:** `feat fix docs chore refactor test ci perf build style revert`;
- **scope:** optional; lowercase letters, digits and hyphens, with commas between several (`(api,world)`);
- **`!`:** marks a breaking change;
- **summary:** doesn't start with a space or end with a period;
- **`(#123)`:** optional, the issues it closes.

The rule lives only in [`tools/pr-title-check.sh`](tools/pr-title-check.sh); its table test is [`tools/pr-title-check.test.sh`](tools/pr-title-check.test.sh).

**Player note:** the description has a line

```
Player note: <one sentence, written like a patch note>
```

- Write it the way patch notes read: third person, starting with what changed, never "I" or "we".
  - "Fixed an issue where heals could raise health above the maximum."
  - "Added browser sign-in to the launcher."
  - "Increased the world server's connection limit."
- For internal work, say so: "No gameplay changes: faster builds."
- The check refuses a note written in the first person.

- It is shown on the public changelog.
- HTML comments don't count, so the template's hint alone fails the check.
- Bots (`renovate[bot]`, `dependabot[bot]`, …) need no note.
- The check blocks merging where branch protection is available (the public repositories: Avalon.Server and this one). In the private repositories it is a red check, not a block. `build` then warns which pull requests had no note, and shows their titles instead.

## Checking pull requests

Add `.github/workflows/pr-check.yml`:

```yaml
name: PR check
on:
  pull_request:
    types: [opened, edited, synchronize, reopened, ready_for_review]
permissions: {}
jobs:
  pr-check:
    name: Title and player note
    runs-on: ubuntu-latest
    steps:
      - uses: WoozChucky/avalon-release-notes/pr-check@v0.1.0
        with:
          title: ${{ github.event.pull_request.title }}
          body: ${{ github.event.pull_request.body }}
          author: ${{ github.event.pull_request.user.login }}
```

The title and body reach the scripts only through environment variables. Pin an exact release tag (Avalon versions stay 0.x until the game's 1.0); Renovate proposes updates.

Use [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) as the template.

## Changelog entries

`build` collects the pull requests merged into `main` between the previous release's commit and this one, and writes one entry:

```bash
GITHUB_TOKEN=… PYTHONPATH=src python -m avalon_release_notes build --repo WoozChucky/Avalon.Server \
  --product server --version 0.7.0 --commit v0.7.0 --previous-commit <previous entry's commit> \
  --published-at 2026-09-28T12:00:00Z --release-url https://github.com/WoozChucky/Avalon.Server/releases/tag/v0.7.0 \
  --public --out entry.json
```

- `--commit` is resolved to its full sha, which the next release's range starts from.
- Without `--previous-commit`, only the released commit's own pull request is taken.
- `--public` (Avalon.Server only) keeps the pull request and release links; the private repositories get text only.

| Title type | Kind | Shown as |
|---|---|---|
| `feat` | `new` | New |
| `perf` | `improved` | Improved |
| `fix` | `fixed` | Fixed |
| any other type | `internal` | collapsed under "internal changes" |
| a bot's pull request | `dependencies` | collapsed, as a dependency update |
| a title from before the convention | `changed` | Changed |

- The item text is the player note. Without one (a bot, or a PR from before the rollout), the text is the title without its `type(scope):` prefix.
- `render --entry entry.json` prints the plain text the game client's manifest carries as its notes.

## Publishing (release jobs)

Install the package with the S3 extra from a tag: `pip install "avalon-release-notes[s3] @ git+https://github.com/WoozChucky/avalon-release-notes@v0.2.0"`. It needs:
- `DIST_S3_ENDPOINT`, `DIST_S3_ACCESS_KEY` and `DIST_S3_SECRET_KEY` (and optionally `DIST_S3_BUCKET`, default `avalon-dist`);
- `GITHUB_TOKEN` with `pull-requests: read`.

The commands:
- `publish` takes the `build` arguments minus `--previous-commit`. It finds the newest entry for the product (and channel) in `avalon-dist`, builds the entry since that commit and uploads it to `changelog/…`. It writes `--out` and `--render-to` if given, and prints the key.
- `previous --product P [--channel C]` prints that commit.
- `upload --entry FILE` uploads an entry built earlier with `build`.

Entries are immutable: uploading the same entry again is fine, and a different one under an existing key is refused. If the GitHub API fails, `publish` stops before writing and says to re-run; the release itself is already out.

## Development

```bash
python -m venv .venv && .venv/Scripts/python -m pip install pytest   # bin/ on Linux
.venv/Scripts/python -m pytest -q
bash tools/pr-title-check.test.sh
```

The package uses the standard library only.
