"""Auxiliary title text search used to evaluate the required text index."""
from __future__ import annotations

import argparse
import json

from common import DEFAULT_URI, get_collection
from queries import jsonable


def search_title(coll, term: str, limit: int = 20):
    return list(
        coll.find(
            {"$text": {"$search": term}},
            {"title": 1, "parent_asin": 1},
        ).limit(max(1, min(limit, 100)))
    )


def explain_title(coll, term: str):
    return coll.find({"$text": {"$search": term}}).explain("executionStats")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("term", nargs="?", default="Laptop")
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--explain", action="store_true")
    p.add_argument("--read-preference", default="secondaryPreferred")
    args = p.parse_args()

    coll, client = get_collection(args.read_preference, args.uri)
    try:
        result = explain_title(coll, args.term) if args.explain else search_title(coll, args.term, args.limit)
        print(json.dumps(jsonable(result), ensure_ascii=False, indent=2))
    finally:
        client.close()
