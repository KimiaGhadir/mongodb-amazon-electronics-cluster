"""Shared MongoDB configuration and Amazon document transformation helpers."""
from __future__ import annotations

import json
import os
from typing import Any

# Project scripts are intentionally designed to run from the Docker `dev`
# service, where these replica-set hostnames are resolvable. Override MONGO_URI
# explicitly if you intentionally use another environment.
DEFAULT_URI = os.getenv(
    "MONGO_URI",
    "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0",
)
DB_NAME = os.getenv("MONGO_DB", "amazon_electronics")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "products")

READ_PREFERENCES = {
    "primary": "PRIMARY",
    "secondary": "SECONDARY",
    "secondaryPreferred": "SECONDARY_PREFERRED",
    "primaryPreferred": "PRIMARY_PREFERRED",
}


def get_client(uri: str = DEFAULT_URI, read_preference: str = "primary"):
    """Create a MongoClient with an explicit read preference.

    Writes are always routed by MongoDB/PyMongo to the current PRIMARY. Query
    scripts use a secondary read preference so reads can be served by replicas.
    """
    from pymongo import MongoClient, ReadPreference

    if read_preference not in READ_PREFERENCES:
        raise ValueError(
            f"Unsupported read preference {read_preference!r}. "
            f"Choose one of: {', '.join(READ_PREFERENCES)}"
        )
    rp = getattr(ReadPreference, READ_PREFERENCES[read_preference])
    return MongoClient(
        uri,
        read_preference=rp,
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
        appname="amazon-electronics-db-project",
    )


def get_collection(read_preference: str = "primary", uri: str = DEFAULT_URI):
    client = get_client(uri, read_preference)
    return client[DB_NAME][COLLECTION_NAME], client


def normalize_value(value: Any) -> Any:
    """Keep details.v consistently indexable while preserving information."""
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return value


def flatten_categories(value: Any) -> list[str]:
    """Flatten a category hierarchy into an ordered, de-duplicated string array.

    The supplied Amazon sample already stores the category path as a flat list,
    but this helper also safely handles nested list/dict forms so the required
    preprocessing step is implemented explicitly rather than assumed.
    """
    result: list[str] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, dict):
            for child in node.values():
                walk(child)
            return
        if isinstance(node, (list, tuple, set)):
            for child in node:
                walk(child)
            return
        text = str(node).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)

    walk(value)
    return result


def transform_record(record: dict) -> dict:
    """Transform one raw Amazon metadata record into the project schema."""
    out = dict(record)
    out["categories"] = flatten_categories(out.get("categories"))

    details = out.get("details") or {}
    if isinstance(details, dict):
        out["details"] = [
            {"k": str(k), "v": normalize_value(v)} for k, v in details.items()
        ]
    elif isinstance(details, list):
        pairs = []
        for item in details:
            if isinstance(item, dict) and "k" in item and "v" in item:
                pairs.append(
                    {"k": str(item["k"]), "v": normalize_value(item["v"])}
                )
        out["details"] = pairs
    else:
        out["details"] = []
    return out
