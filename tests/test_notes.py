from avalon_release_notes.notes import is_bot, player_note

TEMPLATE = """## What

Player note: <!-- Required. One plain sentence a player would understand. -->
"""


def test_reads_the_note():
    assert player_note("## What\nx\n\nPlayer note: Heals no longer lower health.\n") == "Heals no longer lower health."


def test_the_template_hint_alone_is_not_a_note():
    assert player_note(TEMPLATE) is None


def test_a_filled_template_counts():
    body = TEMPLATE.replace("<!-- Required. One plain sentence a player would understand. -->", "<!-- hint -->Faster builds.")
    assert player_note(body) == "Faster builds."


def test_missing_or_empty_is_none():
    assert player_note(None) is None
    assert player_note("no note here") is None
    assert player_note("Player note:   \n") is None


def test_accepts_bold_and_list_forms():
    assert player_note("**Player note:** Faster builds.") == "Faster builds."
    assert player_note("- Player note: Faster builds.") == "Faster builds."
    assert player_note("player NOTE: x") == "x"


def test_the_first_note_wins():
    assert player_note("Player note: a\nPlayer note: b") == "a"


def test_bots():
    assert is_bot("renovate[bot]") and is_bot("dependabot[bot]")
    assert not is_bot("WoozChucky") and not is_bot(None)


def test_first_person_is_spotted():
    from avalon_release_notes.notes import first_person
    for note in ("I fixed the heals.", "We now cap health.", "Fixed my mistake in the loot table.",
                 "Our servers restart faster.", "Heals no longer confuse us.", "I've added a launcher setting."):
        assert first_person(note), note
    for note in ("Fixed an issue where heals could raise health above the maximum.",
                 "Added browser sign-in to the launcher.", "The US realm list loads faster.",
                 "Improved world server start-up time.", "No gameplay changes: CI now checks pull request titles."):
        assert not first_person(note), note
