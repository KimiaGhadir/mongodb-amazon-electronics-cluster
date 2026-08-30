"""Streaming JSONL ingestion for the Amazon Electronics metadata dataset."""
from __future__ import annotations

import argparse
import json
import time

from pymongo.errors import BulkWriteError

from common import COLLECTION_NAME, DB_NAME, DEFAULT_URI, transform_record


def stream_records(path: str, batch_size: int):
    """Read a JSONL file line-by-line and yield transformed batches."""
    batch = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc
            batch.append(transform_record(record))
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def ingest(
    path: str,
    uri: str = DEFAULT_URI,
    db_name: str = DB_NAME,
    collection_name: str = COLLECTION_NAME,
    batch_size: int = 1000,
    drop: bool = False,
    max_records: int | None = None,
):
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    coll = client[db_name][collection_name]
    client.admin.command("ping")

    if drop:
        coll.drop()

    inserted = 0
    started = time.perf_counter()
    batch_size = max(1, batch_size)

    for batch in stream_records(path, batch_size):
        if max_records is not None:
            remaining = max_records - inserted
            if remaining <= 0:
                break
            batch = batch[:remaining]
        if not batch:
            break

        try:
            coll.insert_many(batch, ordered=False)
        except BulkWriteError as exc:
            write_errors = exc.details.get("writeErrors", [])
            non_duplicate_errors = [e for e in write_errors if e.get("code") != 11000]
            write_concern_errors = exc.details.get("writeConcernErrors", [])
            if non_duplicate_errors or write_concern_errors:
                raise
            # Only duplicate-key errors are intentionally tolerated.
            inserted += len(batch) - len(write_errors)
        else:
            inserted += len(batch)

        if inserted and inserted % (batch_size * 10) == 0:
            print(f"Inserted {inserted:,} records")

    elapsed = time.perf_counter() - started
    result = {
        "inserted": inserted,
        "seconds": elapsed,
        "records_per_second": inserted / elapsed if elapsed else None,
    }
    print(json.dumps(result, indent=2))
    client.close()
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", help="Path to the Amazon Electronics JSONL file")
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--db", default=DB_NAME)
    p.add_argument("--collection", default=COLLECTION_NAME)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--drop", action="store_true")
    p.add_argument("--max-records", type=int)
    args = p.parse_args()
    ingest(
        args.path,
        args.uri,
        args.db,
        args.collection,
        args.batch_size,
        args.drop,
        args.max_records,
    )
