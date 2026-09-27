"""Changelog entries in avalon-dist: one immutable JSON object per release (spec section 4)."""
import json
import os

from botocore.exceptions import ClientError


class EntryConflict(RuntimeError):
    pass


def entry_key(product: str, channel: str | None, version: str, build: str | None) -> str:
    if product == "client":
        return f"changelog/client/{channel}/{build}.json"
    return f"changelog/{product}/{version}.json"


def _prefix(product: str, channel: str | None) -> str:
    return f"changelog/client/{channel}/" if product == "client" else f"changelog/{product}/"


def _encode(entry: dict) -> bytes:
    return (json.dumps(entry, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class Store:
    def __init__(self, client, bucket: str):
        self.client, self.bucket = client, bucket

    def _read(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def latest(self, product: str, channel: str | None) -> dict | None:
        newest = None
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=_prefix(product, channel)):
            for obj in page.get("Contents", []):
                entry = json.loads(self._read(obj["Key"]))
                if newest is None or entry["publishedAt"] > newest["publishedAt"]:
                    newest = entry
        return newest

    def put(self, entry: dict) -> str:
        key = entry_key(entry["product"], entry["channel"], entry["version"], entry["build"])
        body = _encode(entry)
        existing = self._read(key)
        if existing is not None and json.loads(existing) != entry:
            raise EntryConflict(f"{key} already holds a different entry; entries are immutable")
        if existing is None:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")
        return key


def from_env() -> Store:
    import boto3

    client = boto3.client("s3", endpoint_url=os.environ["DIST_S3_ENDPOINT"], region_name="garage",
                          aws_access_key_id=os.environ["DIST_S3_ACCESS_KEY"],
                          aws_secret_access_key=os.environ["DIST_S3_SECRET_KEY"],
                          config=boto3.session.Config(s3={"addressing_style": "path"}))
    return Store(client, os.environ.get("DIST_S3_BUCKET", "avalon-dist"))
