"""Benchmark the five required query classes in the three required modes."""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import time

from common import DB_NAME, COLLECTION_NAME, get_collection
from indexes import PROJECT_INDEX_NAMES
from queries import q1_by_asin, q2_paginate, q3_category, q4_feature, q5_features
from workload import load_or_create_workload

MODES = ("standalone_no_index", "cluster_no_index", "optimized_cluster")


def percentile(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    idx = (len(xs) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(xs) - 1)
    fraction = idx - lo
    return xs[lo] * (1 - fraction) + xs[hi] * fraction


def verify_mode(client, coll, mode: str):
    """Fail fast if the selected deployment does not match the benchmark label."""
    hello = client.admin.command("hello")
    is_replica_set = bool(hello.get("setName"))
    index_names = {idx["name"] for idx in coll.list_indexes()}
    project_indexes = PROJECT_INDEX_NAMES & index_names

    if mode == "standalone_no_index":
        if is_replica_set:
            raise RuntimeError("standalone_no_index points to a Replica Set, not a standalone MongoDB.")
        if project_indexes:
            raise RuntimeError(f"Standalone benchmark must have no project indexes; found {sorted(project_indexes)}")
    elif mode == "cluster_no_index":
        if not is_replica_set:
            raise RuntimeError("cluster_no_index must point to the rs0 Replica Set.")
        if project_indexes:
            raise RuntimeError(f"cluster_no_index must have no project indexes; found {sorted(project_indexes)}")
    elif mode == "optimized_cluster":
        if not is_replica_set:
            raise RuntimeError("optimized_cluster must point to the rs0 Replica Set.")
        missing = PROJECT_INDEX_NAMES - index_names
        if missing:
            raise RuntimeError(f"optimized_cluster is missing indexes: {sorted(missing)}")


def build_tests(coll, workload):
    return [
        ("Q1", lambda: q1_by_asin(coll, workload["q1_asin"])),
        ("Q2", lambda: q2_paginate(coll, 1, 20)),
        ("Q3", lambda: q3_category(coll, workload["q3_category"])),
        ("Q4", lambda: q4_feature(coll, workload["q4"]["k"], workload["q4"]["v"])),
        ("Q5_AND", lambda: q5_features(coll, workload["q5_and"], "AND")),
        ("Q5_OR", lambda: q5_features(coll, workload["q5_or"], "OR")),
    ]


def benchmark(coll, workload, repeats: int, warmup: int):
    rows = []
    for name, fn in build_tests(coll, workload):
        for _ in range(max(0, warmup)):
            fn()

        times = []
        for _ in range(repeats):
            started = time.perf_counter()
            fn()
            times.append((time.perf_counter() - started) * 1000)

        rows.append(
            {
                "query": name,
                "runs": repeats,
                "avg_ms": statistics.mean(times),
                "p50_ms": percentile(times, 0.50),
                "p95_ms": percentile(times, 0.95),
                "min_ms": min(times),
                "max_ms": max(times),
            }
        )
    return rows


def write_mode_results(path: str, mode: str, rows: list[dict]):
    fields = ["mode", "query", "runs", "avg_ms", "p50_ms", "p95_ms", "min_ms", "max_ms"]
    existing = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            existing = [row for row in csv.DictReader(f) if row.get("mode") != mode]

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in existing:
            writer.writerow({field: row.get(field, "") for field in fields})
        for row in rows:
            writer.writerow({"mode": mode, **row})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", required=True, choices=MODES)
    p.add_argument("--uri", required=True)
    p.add_argument(
        "--read-preference",
        choices=["primary", "secondary", "secondaryPreferred", "primaryPreferred"],
        help="Defaults to primary for standalone and secondaryPreferred for cluster modes.",
    )
    p.add_argument("--repeats", type=int, default=30)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--workload", default="results/workload.json")
    p.add_argument("--out", default="results/benchmark.csv")
    args = p.parse_args()

    if args.repeats <= 0:
        p.error("--repeats must be positive")

    read_preference = args.read_preference or (
        "primary" if args.mode == "standalone_no_index" else "secondaryPreferred"
    )
    coll, client = get_collection(read_preference, args.uri)
    try:
        client.admin.command("ping")
        verify_mode(client, coll, args.mode)
        workload = load_or_create_workload(coll, args.workload)
        rows = benchmark(coll, workload, args.repeats, args.warmup)
        write_mode_results(args.out, args.mode, rows)
        print(f"Mode: {args.mode}")
        print(f"Read preference: {read_preference}")
        print(f"Database: {DB_NAME}.{COLLECTION_NAME}")
        print(f"Workload: {workload}")
        for row in rows:
            print(row)
        print(f"Saved results to {args.out}")
    finally:
        client.close()
