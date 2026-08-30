"""The five required operational query classes, with explain support."""
from __future__ import annotations

import argparse
import json
from typing import Iterable

from common import DEFAULT_URI, get_collection


def q1_by_asin(coll, asin: str):
    return coll.find_one({"parent_asin": asin})


def q2_paginate(coll, page: int = 1, page_size: int = 20):
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    return list(
        coll.find({}, {"title": 1, "parent_asin": 1, "price": 1})
        .sort("parent_asin", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )


def q3_category(coll, category: str):
    return list(coll.find({"categories": category}))


def q4_feature(coll, key: str, value):
    return list(coll.find({"details": {"$elemMatch": {"k": key, "v": value}}}))


def q5_features(coll, conditions: Iterable[dict], mode: str = "AND"):
    clauses = [
        {"details": {"$elemMatch": {"k": c["k"], "v": c["v"]}}}
        for c in conditions
    ]
    if not clauses:
        return []
    filt = {"$or": clauses} if mode.upper() == "OR" else {"$and": clauses}
    return list(coll.find(filt))


def explain_q1(coll, asin):
    return coll.find({"parent_asin": asin}).explain()


def explain_q2(coll, page=1, page_size=20):
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    return (
        coll.find({})
        .sort("parent_asin", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .explain()
    )


def explain_q3(coll, category):
    return coll.find({"categories": category}).explain()


def explain_q4(coll, key, value):
    return coll.find(
        {"details": {"$elemMatch": {"k": key, "v": value}}}
    ).explain()


def explain_q5(coll, conditions, mode):
    clauses = [
        {"details": {"$elemMatch": {"k": c["k"], "v": c["v"]}}}
        for c in conditions
    ]
    filt = {"$or": clauses} if mode.upper() == "OR" else {"$and": clauses}
    return coll.find(filt).explain()


def jsonable(obj):
    return json.loads(json.dumps(obj, default=str))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("query", choices=["q1", "q2", "q3", "q4", "q5"])
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument(
        "--read-preference",
        choices=["primary", "secondary", "secondaryPreferred", "primaryPreferred"],
        default="secondaryPreferred",
    )
    p.add_argument("--asin")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=20)
    p.add_argument("--category", default="Laptops")
    p.add_argument("--key", default="Resolution")
    p.add_argument("--value", default="4K")
    p.add_argument("--mode", choices=["AND", "OR"], default="AND")
    p.add_argument(
        "--conditions",
        default='[{"k":"Date First Available","v":"August 2, 2014"},{"k":"Manufacturer","v":"Fatshark"}]',
    )
    p.add_argument("--explain", action="store_true")
    args = p.parse_args()

    coll, client = get_collection(args.read_preference, args.uri)
    try:
        if args.query == "q1":
            if not args.asin:
                p.error("--asin is required for q1")
            result = explain_q1(coll, args.asin) if args.explain else q1_by_asin(coll, args.asin)
        elif args.query == "q2":
            result = explain_q2(coll, args.page, args.page_size) if args.explain else q2_paginate(coll, args.page, args.page_size)
        elif args.query == "q3":
            result = explain_q3(coll, args.category) if args.explain else q3_category(coll, args.category)
        elif args.query == "q4":
            result = explain_q4(coll, args.key, args.value) if args.explain else q4_feature(coll, args.key, args.value)
        else:
            conditions = json.loads(args.conditions)
            result = explain_q5(coll, conditions, args.mode) if args.explain else q5_features(coll, conditions, args.mode)
        print(json.dumps(jsonable(result), ensure_ascii=False, indent=2))
    finally:
        client.close()

