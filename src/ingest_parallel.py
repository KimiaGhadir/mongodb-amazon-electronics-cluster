"""Parallel streaming ingestion for the Amazon Electronics metadata dataset.

The input file is split into non-overlapping byte ranges. Each worker aligns to
JSONL line boundaries, then reads its own range sequentially, line-by-line.
Memory usage is bounded by roughly workers * batch_size documents.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from typing import Iterator

from pymongo.errors import BulkWriteError

from common import COLLECTION_NAME, DB_NAME, DEFAULT_URI, transform_record


def iter_segment_lines(path: str, start: int, end: int, is_last: bool) -> Iterator[tuple[int, bytes]]:
    """Yield complete JSONL records whose starting byte belongs to [start, end)."""
    with open(path, "rb") as f:
        if start > 0:
            # If start is in the middle of a line, discard only that remainder.
            # If it is already on a line boundary, keep the line at `start`.
            f.seek(start - 1)
            previous = f.read(1)
            if previous != b"\n":
                f.readline()
        else:
            f.seek(0)

        while True:
            line_start = f.tell()
            if not is_last and line_start >= end:
                break

            line = f.readline()
            if not line:
                break
            if not line.strip():
                continue
            yield line_start, line


def insert_batch(coll, docs: list[dict]) -> int:
    """Insert a batch and tolerate duplicate-key errors only."""
    try:
        coll.insert_many(docs, ordered=False)
        return len(docs)
    except BulkWriteError as exc:
        details = exc.details or {}
        write_errors = details.get("writeErrors", [])
        non_duplicate_errors = [e for e in write_errors if e.get("code") != 11000]
        write_concern_errors = details.get("writeConcernErrors", [])
        if non_duplicate_errors or write_concern_errors:
            raise
        return len(docs) - len(write_errors)


def worker_ingest(args: tuple) -> dict:
    (
        worker_id,
        path,
        start,
        end,
        is_last,
        uri,
        db_name,
        collection_name,
        batch_size,
    ) = args

    # Import here so every spawned worker creates its own MongoClient/pool.
    from pymongo import MongoClient

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
        maxPoolSize=8,
        appname=f"amazon-electronics-parallel-ingest-{worker_id}",
    )
    coll = client[db_name][collection_name]
    client.admin.command("ping")

    inserted = 0
    batch: list[dict] = []
    started = time.perf_counter()
    next_report = 10_000

    try:
        for byte_pos, raw_line in iter_segment_lines(path, start, end, is_last):
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError(
                    f"Worker {worker_id}: invalid JSON near byte {byte_pos}: {exc}"
                ) from exc

            batch.append(transform_record(record))
            if len(batch) >= batch_size:
                inserted += insert_batch(coll, batch)
                batch = []

                if inserted >= next_report:
                    print(
                        f"[worker {worker_id}] inserted {inserted:,} records",
                        flush=True,
                    )
                    next_report = ((inserted // 10_000) + 1) * 10_000

        if batch:
            inserted += insert_batch(coll, batch)

        elapsed = time.perf_counter() - started
        result = {
            "worker": worker_id,
            "inserted": inserted,
            "seconds": elapsed,
            "records_per_second": inserted / elapsed if elapsed else None,
        }
        print(json.dumps(result), flush=True)
        return result
    finally:
        client.close()


def parallel_ingest(
    path: str,
    uri: str = DEFAULT_URI,
    db_name: str = DB_NAME,
    collection_name: str = COLLECTION_NAME,
    batch_size: int = 1000,
    workers: int = 4,
    drop: bool = False,
) -> dict:
    from pymongo import MongoClient

    workers = max(1, workers)
    batch_size = max(1, batch_size)
    file_size = os.path.getsize(path)

    # Drop exactly once, before any parallel writer starts.
    admin_client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    admin_client.admin.command("ping")
    coll = admin_client[db_name][collection_name]
    if drop:
        print(f"Dropping {db_name}.{collection_name} ...", flush=True)
        coll.drop()
    admin_client.close()

    jobs = []
    for i in range(workers):
        start = file_size * i // workers
        end = file_size * (i + 1) // workers
        jobs.append(
            (
                i + 1,
                path,
                start,
                end,
                i == workers - 1,
                uri,
                db_name,
                collection_name,
                batch_size,
            )
        )

    print(
        f"Starting parallel streaming import: workers={workers}, "
        f"batch_size={batch_size}, file_bytes={file_size:,}",
        flush=True,
    )

    started = time.perf_counter()
    # spawn avoids inheriting a MongoClient across process boundaries.
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        results = pool.map(worker_ingest, jobs)

    elapsed = time.perf_counter() - started
    total = sum(r["inserted"] for r in results)
    result = {
        "inserted": total,
        "seconds": elapsed,
        "records_per_second": total / elapsed if elapsed else None,
        "workers": workers,
        "batch_size": batch_size,
    }
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", help="Path to the Amazon Electronics JSONL file")
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--db", default=DB_NAME)
    p.add_argument("--collection", default=COLLECTION_NAME)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--drop", action="store_true")
    args = p.parse_args()

    parallel_ingest(
        args.path,
        args.uri,
        args.db,
        args.collection,
        args.batch_size,
        args.workers,
        args.drop,
    )
