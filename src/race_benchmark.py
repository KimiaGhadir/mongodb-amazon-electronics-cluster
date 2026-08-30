"""Concurrent update pressure test for the race-condition requirement."""
from __future__ import annotations

import argparse
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor

from common import COLLECTION_NAME, DB_NAME, DEFAULT_URI
from race_condition import DEMO_FIELD, atomic_increment, choose_product, reset_product, unsafe_increment


def run_one(coll, product_id, method: str, workers: int, operations: int, delay: float):
    reset_product(coll, product_id)
    fn = unsafe_increment if method == "unsafe" else atomic_increment

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        acknowledgements = list(
            executor.map(lambda _: fn(coll, product_id, delay), range(operations))
        )
    elapsed = time.perf_counter() - started

    final = int(coll.find_one({"_id": product_id}, {DEMO_FIELD: 1})[DEMO_FIELD])
    successful = sum(bool(x) for x in acknowledgements)
    return {
        "method": method,
        "workers": workers,
        "operations": operations,
        "successful_requests": successful,
        "elapsed_s": elapsed,
        "throughput_req_s": successful / elapsed if elapsed else None,
        "final_value": final,
        "expected_value": operations,
        "lost_updates": operations - final,
    }


def parse_workers(value: str) -> list[int]:
    workers = sorted({int(x.strip()) for x in value.split(",") if x.strip()})
    if not workers or any(x <= 0 for x in workers):
        raise argparse.ArgumentTypeError("--workers must contain positive integers, e.g. 10,25,50,100")
    return workers


def write_results(path: str, rows: list[dict]):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = [
        "method",
        "workers",
        "operations",
        "successful_requests",
        "elapsed_s",
        "throughput_req_s",
        "final_value",
        "expected_value",
        "lost_updates",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--db", default=DB_NAME)
    p.add_argument("--asin")
    p.add_argument("--workers", type=parse_workers, default=parse_workers("10,25,50,100"))
    p.add_argument("--operations", type=int, default=500)
    p.add_argument("--delay", type=float, default=0.002)
    p.add_argument("--out", default="results/race_benchmark.csv")
    args = p.parse_args()

    if args.operations <= 0:
        p.error("--operations must be positive")

    from pymongo import MongoClient

    client = MongoClient(args.uri, serverSelectionTimeoutMS=10_000)
    coll = client[args.db][COLLECTION_NAME]
    client.admin.command("ping")
    product_id, selected_asin = choose_product(coll, args.asin)
    print(f"Using product parent_asin={selected_asin}")

    rows = []
    for workers in args.workers:
        for method in ("unsafe", "atomic"):
            row = run_one(coll, product_id, method, workers, args.operations, args.delay)
            rows.append(row)
            print(row)

    write_results(args.out, rows)
    print(f"Saved {len(rows)} rows to {args.out}")
    client.close()
