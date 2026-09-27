from avalon_release_notes.entry import PullRequest, build_entry, make_item, render_text


def pr(n, title, body="Player note: Note %d.", author="WoozChucky", merged="2026-09-27T12:00:0%dZ"):
    return PullRequest(n, title, body % n if "%d" in body else body, author, merged % (n % 10), f"https://gh/pull/{n}")


def test_kinds_follow_the_title_type():
    kinds = [make_item(pr(n, t), public=False)["kind"] for n, t in [
        (1, "feat: a"), (2, "perf(world): b"), (3, "fix: c"), (4, "ci: d"), (5, "Auth: old style")]]
    assert kinds == ["new", "improved", "fixed", "internal", "changed"]


def test_bot_prs_are_dependencies_titled_by_their_summary():
    item = make_item(pr(6, "chore(deps): update xunit to v3", body="", author="renovate[bot]"), public=False)
    assert item == {"kind": "dependencies", "text": "update xunit to v3", "breaking": False}


def test_the_note_is_the_text_and_breaking_is_kept():
    item = make_item(pr(7, "feat(api)!: drop v1"), public=False)
    assert item["text"] == "Note 7." and item["breaking"] is True


def test_a_missing_note_falls_back_to_the_summary():
    assert make_item(pr(8, "fix(world): heals cap at max", body="no note"), public=False)["text"] == "heals cap at max"


def test_public_items_link_their_pr_private_ones_do_not():
    assert make_item(pr(9, "fix: x"), public=True)["prUrl"] == "https://gh/pull/9"
    assert "pr" not in make_item(pr(9, "fix: x"), public=False)


def test_build_entry_orders_items_by_merge_time_and_hides_release_url_for_private():
    e = build_entry(product="client", channel="ptr", version="0.1.0", build="0.1.0+5.abc", commit="c" * 40,
                    published_at="2026-09-27T18:00:00Z", release_url="https://x", public=False,
                    prs=[pr(2, "fix: b"), pr(1, "feat: a")])
    assert [i["text"] for i in e["items"]] == ["Note 1.", "Note 2."]
    assert e["releaseUrl"] is None and e["schema"] == 1 and e["channel"] == "ptr"


def test_render_text_groups_and_counts_internal():
    e = build_entry(product="client", channel="ptr", version="v", build="b", commit="c", published_at="t",
                    release_url=None, public=False,
                    prs=[pr(1, "feat: a"), pr(2, "fix(x)!: b"), pr(3, "ci: c"), pr(4, "chore(deps): d", body="", author="renovate[bot]")])
    assert render_text(e) == "New:\n- Note 1.\n\nFixed:\n- Note 2. (breaking)\n\nAlso: 2 internal changes"


def test_render_text_without_player_facing_changes():
    e = build_entry(product="server", channel=None, version="v", build=None, commit="c", published_at="t",
                    release_url=None, public=True, prs=[pr(3, "ci: c")])
    assert render_text(e) == "No player-facing changes.\nAlso: 1 internal change"
    empty = dict(e, items=[])
    assert render_text(empty) == "No player-facing changes."
