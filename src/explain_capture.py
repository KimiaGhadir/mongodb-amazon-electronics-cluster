"""Capture executionStats for all five required queries into JSON files."""
from __future__ import annotations

import argparse
import json
import os

from common import DEFAULT_URI, get_collection
from queries import explain_q1, explain_q2, explain_q3, explain_q4, explain_q5, jsonable
from workload import load_or_create_workload


def capture(coll, workload):
    return {
        "Q1": explain_q1(coll, workload["q1_asin"]),
        "Q2": explain_q2(coll, 1, 20),
        "Q3": explain_q3(coll, workload["q3_category"]),
        "Q4": explain_q4(coll, workload["q4"]["k"], workload["q4"]["v"]),
        "Q5_AND": explain_q5(coll, workload["q5_and"], "AND"),
        "Q5_OR": explain_q5(coll, workload["q5_or"], "OR"),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True, help="Example: cluster_no_index or optimized_cluster")
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--read-preference", default="secondaryPreferred")
    p.add_argument("--workload", default="results/workload.json")
    p.add_argument("--out-dir", default="results/explain")
    args = p.parse_args()

    coll, client = get_collection(args.read_preference, args.uri)
    try:
        workload = load_or_create_workload(coll, args.workload)
        results = capture(coll, workload)
        target = os.path.join(args.out_dir, args.label)
        os.makedirs(target, exist_ok=True)
        for name, value in results.items():
            path = os.path.join(target, f"{name.lower()}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(jsonable(value), f, ensure_ascii=False, indent=2)
            print(path)
    finally:
        client.close()
