"""Demonstrate a lost update on a real product and fix it with atomic $inc."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

from common import COLLECTION_NAME, DB_NAME, DEFAULT_URI

DEMO_FIELD = "demo_views"


def choose_product(coll, asin: str | None = None):
    filt = {"parent_asin": asin} if asin else {"parent_asin": {"$exists": True, "$ne": None}}
    doc = coll.find_one(filt, {"parent_asin": 1})
    if not doc:
        raise RuntimeError("No matching product found. Ingest data first or choose another --asin.")
    return doc["_id"], doc.get("parent_asin")


def reset_product(coll, product_id, value: int = 0):
    coll.update_one({"_id": product_id}, {"$set": {DEMO_FIELD: value}})


def unsafe_increment(coll, product_id, delay: float) -> bool:
    """Read-modify-write: vulnerable to lost updates."""
    doc = coll.find_one({"_id": product_id}, {DEMO_FIELD: 1})
    current = int(doc.get(DEMO_FIELD, 0))
    if delay:
        time.sleep(delay)
    result = coll.update_one({"_id": product_id}, {"$set": {DEMO_FIELD: current + 1}})
    return bool(result.acknowledged)


def atomic_increment(coll, product_id, delay: float) -> bool:
    """Single-document atomic update: safe under concurrent writers."""
    if delay:
        time.sleep(delay)
    result = coll.update_one({"_id": product_id}, {"$inc": {DEMO_FIELD: 1}})
    return bool(result.acknowledged)


def execute(coll, product_id, workers: int, method: str, delay: float):
    fn = unsafe_increment if method == "unsafe" else atomic_increment
    with ThreadPoolExecutor(max_workers=workers) as executor:
        acknowledgements = list(
            executor.map(lambda _: fn(coll, product_id, delay), range(workers))
        )
    final = coll.find_one({"_id": product_id}, {DEMO_FIELD: 1})[DEMO_FIELD]
    return sum(bool(x) for x in acknowledgements), int(final)


def run(workers: int, uri: str, db_name: str, asin: str | None, delay: float):
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    coll = client[db_name][COLLECTION_NAME]
    client.admin.command("ping")
    product_id, selected_asin = choose_product(coll, asin)

    reset_product(coll, product_id)
    unsafe_success, unsafe_final = execute(coll, product_id, workers, "unsafe", delay)

    reset_product(coll, product_id)
    safe_success, safe_final = execute(coll, product_id, workers, "atomic", delay)

    result = {
        "product_asin": selected_asin,
        "field": DEMO_FIELD,
        "workers": workers,
        "expected_final": workers,
        "unsafe": {
            "acknowledged_updates": unsafe_success,
            "final_value": unsafe_final,
            "lost_updates": workers - unsafe_final,
        },
        "atomic_inc": {
            "acknowledged_updates": safe_success,
            "final_value": safe_final,
            "lost_updates": workers - safe_final,
        },
    }
    print(json.dumps(result, indent=2))
    client.close()
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=50)
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--db", default=DB_NAME)
    p.add_argument("--asin")
    p.add_argument(
        "--delay",
        type=float,
        default=0.005,
        help="Artificial application delay in seconds to make the lost-update race visible.",
    )
    args = p.parse_args()
    run(args.workers, args.uri, args.db, args.asin, args.delay)
