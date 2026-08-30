"""Choose and persist a real query workload from the loaded dataset."""
from __future__ import annotations

import json
import os
from typing import Any


def _pair(item: dict[str, Any]) -> dict[str, Any]:
    return {"k": item["k"], "v": item["v"]}


def discover_workload(coll) -> dict[str, Any]:
    """Select values that are guaranteed to exist in the current collection."""
    base = coll.find_one(
        {"parent_asin": {"$exists": True, "$ne": None}},
        {"parent_asin": 1, "categories": 1, "details": 1},
    )
    if not base:
        raise RuntimeError("The products collection is empty. Ingest data first.")

    category_doc = coll.find_one(
        {"categories.0": {"$exists": True}},
        {"categories": 1},
    )
    detail_doc = coll.find_one(
        {"details.0": {"$exists": True}},
        {"details": 1},
    )
    and_doc = coll.find_one(
        {"details.1": {"$exists": True}},
        {"details": 1},
    )
    if not category_doc or not detail_doc or not and_doc:
        raise RuntimeError(
            "Loaded data does not contain enough categories/details for the required workload."
        )

    q4 = _pair(detail_doc["details"][0])
    q5_and = [_pair(and_doc["details"][0]), _pair(and_doc["details"][1])]

    # Pick a second real feature for OR if possible. Reusing real features keeps
    # the benchmark valid on both the 500-row sample and the full dataset.
    or_doc = coll.find_one(
        {
            "details.0": {"$exists": True},
            "_id": {"$ne": and_doc["_id"]},
        },
        {"details": 1},
    )
    second_or = _pair(or_doc["details"][0]) if or_doc else q5_and[1]

    return {
        "q1_asin": base["parent_asin"],
        "q3_category": category_doc["categories"][-1],
        "q4": q4,
        "q5_and": q5_and,
        "q5_or": [q5_and[0], second_or],
    }


def load_or_create_workload(coll, path: str) -> dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    workload = discover_workload(coll)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workload, f, ensure_ascii=False, indent=2, default=str)
    return workload
