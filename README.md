# avalon-release-notes

The pull request conventions every Avalon repository follows, and the tool that turns merged pull requests into the public changelog (homelab spec `docs/superpowers/specs/2026-09-27-avalon-changelog-design.md`).

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
Player note: <one plain sentence a player would understand>
```

- It says what a player will notice. For internal work, say what it means, e.g. "Faster builds; nothing changes in the game".
- It is shown on the public changelog.
- HTML comments don't count, so the template's hint alone fails the check.
- Bots (`renovate[bot]`, `dependabot[bot]`, …) need no note.

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
      - uses: WoozChucky/avalon-release-notes/pr-check@v1
        with:
          title: ${{ github.event.pull_request.title }}
          body: ${{ github.event.pull_request.body }}
          author: ${{ github.event.pull_request.user.login }}
```

The title and body reach the scripts only through environment variables.

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

## Development

```bash
python -m venv .venv && .venv/Scripts/python -m pip install pytest   # bin/ on Linux
.venv/Scripts/python -m pytest -q
bash tools/pr-title-check.test.sh
```

The package uses the standard library only.
