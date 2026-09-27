import json

import boto3
import pytest
from moto import mock_aws

from avalon_release_notes.store import EntryConflict, Store, entry_key

BUCKET = "avalon-dist"


def entry(product="server", channel=None, version="0.6.0", build=None, commit="c" * 40, at="2026-09-27T14:00:00Z", items=()):
    return {"schema": 1, "product": product, "channel": channel, "version": version, "build": build,
            "commit": commit, "publishedAt": at, "releaseUrl": None, "items": list(items)}


@pytest.fixture
def store():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        yield Store(s3, BUCKET)


def test_keys_follow_the_spec():
    assert entry_key("server", None, "0.6.0", None) == "changelog/server/0.6.0.json"
    assert entry_key("launcher", None, "0.1.1", None) == "changelog/launcher/0.1.1.json"
    assert entry_key("client", "ptr", "0.1.0", "0.1.0+4.a33bb7c") == "changelog/client/ptr/0.1.0+4.a33bb7c.json"


def test_previous_is_the_newest_by_published_at(store):
    store.put(entry(version="0.5.0", commit="a" * 40, at="2026-09-27T11:00:00Z"))
    store.put(entry(version="0.10.0", commit="b" * 40, at="2026-09-28T11:00:00Z"))
    store.put(entry(version="0.6.0", commit="c" * 40, at="2026-09-27T14:00:00Z"))
    assert store.latest("server", None)["commit"] == "b" * 40


def test_client_channels_are_separate(store):
    store.put(entry("client", "ptr", "0.1.0", "0.1.0+4.x", commit="p" * 40))
    assert store.latest("client", "dev") is None
    assert store.latest("client", "ptr")["commit"] == "p" * 40


def test_re_uploading_the_same_entry_is_fine(store):
    e = entry()
    assert store.put(e) == store.put(dict(e)) == "changelog/server/0.6.0.json"


def test_refuses_to_overwrite_a_different_entry(store):
    store.put(entry())
    with pytest.raises(EntryConflict):
        store.put(entry(items=[{"kind": "fixed", "text": "x", "breaking": False}]))
