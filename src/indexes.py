"""Create, inspect, or drop the project indexes."""
from __future__ import annotations

import argparse
from pymongo import ASCENDING, TEXT
from pymongo.errors import DuplicateKeyError, OperationFailure

from common import DEFAULT_URI, get_collection

PROJECT_INDEX_NAMES = {
    "idx_parent_asin",
    "idx_categories",
    "idx_details_kv",
    "idx_title_text",
}


def create_indexes(coll) -> list[str]:
    """Create indexes justified by the required query workload.

    - parent_asin: point lookup (Q1), unique application identifier
    - categories: multikey category membership search (Q3)
    - details.k + details.v: compound multikey feature filters (Q4/Q5)
    - title text: explicit text-index evaluation required by the assignment's
      indexing section; it is an auxiliary search, not one of the five queries.
    """
    names: list[str] = []
    try:
        names.append(
            coll.create_index(
                [("parent_asin", ASCENDING)],
                unique=True,
                name="idx_parent_asin",
            )
        )
    except (DuplicateKeyError, OperationFailure) as exc:
        raise RuntimeError(
            "Could not create the unique parent_asin index. The collection may "
            "contain duplicate/missing parent_asin values. Clean the data and retry."
        ) from exc

    names.append(coll.create_index([("categories", ASCENDING)], name="idx_categories"))
    names.append(
        coll.create_index(
            [("details.k", ASCENDING), ("details.v", ASCENDING)],
            name="idx_details_kv",
        )
    )
    names.append(coll.create_index([("title", TEXT)], name="idx_title_text"))
    return names


def drop_project_indexes(coll) -> list[str]:
    existing = {idx["name"] for idx in coll.list_indexes()}
    dropped: list[str] = []
    for name in sorted(PROJECT_INDEX_NAMES & existing):
        coll.drop_index(name)
        dropped.append(name)
    return dropped


def list_indexes(coll) -> list[dict]:
    return [dict(index) for index in coll.list_indexes()]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["create", "drop", "list"])
    p.add_argument("--read-preference", default="primary")
    p.add_argument("--uri", default=DEFAULT_URI)
    args = p.parse_args()

    coll, client = get_collection(args.read_preference, args.uri)
    try:
        if args.action == "create":
            print("Created/verified indexes:", create_indexes(coll))
        elif args.action == "drop":
            print("Dropped indexes:", drop_project_indexes(coll))
        else:
            for item in list_indexes(coll):
                print(item)
    finally:
        client.close()
