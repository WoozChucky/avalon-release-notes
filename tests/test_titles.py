from avalon_release_notes.titles import Title, parse_title


def test_parses_type_scope_breaking_and_summary():
    assert parse_title("feat(api,world)!: key presence by world (#556)") == Title(
        "feat", "api,world", True, "key presence by world"
    )


def test_a_title_without_scope_or_reference():
    assert parse_title("fix: heals no longer lower health") == Title("fix", None, False, "heals no longer lower health")


def test_several_issue_references_are_removed():
    assert parse_title("fix(world): x (#1, #2)").summary == "x"


def test_a_non_conventional_title_keeps_its_text():
    assert parse_title("Auth: budget world selects per connection (#574)") == Title(
        None, None, False, "Auth: budget world selects per connection (#574)"
    )


def test_an_unknown_type_is_not_conventional():
    assert parse_title("feature(api): x").type is None
