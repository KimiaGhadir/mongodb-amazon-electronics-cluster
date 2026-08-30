"""Resumable, serial, streaming JSONL ingestion for Amazon Electronics metadata.

Design goals:
- Single-process / line-by-line streaming (project requirement).
- Stable _id derived from parent_asin, so retries/resume are idempotent.
- Host-side checkpoint by byte offset.
- Retry transient PyMongo/network failures.
- Unordered bulk insert; duplicate-key errors are tolerated on retry.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import BulkWriteError, PyMongoError

from common import COLLECTION_NAME, DB_NAME, DEFAULT_URI, transform_record


def load_checkpoint(checkpoint_path: Path, source_path: Path) -> dict:
    if not checkpoint_path.exists():
        return {"offset": 0, "inserted": 0}

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    current_size = source_path.stat().st_size

    if data.get("source_size") != current_size:
        raise RuntimeError(
            "Checkpoint belongs to a different source file size. "
            "Delete the checkpoint or run again with --drop."
        )
    return data


def save_checkpoint(
    checkpoint_path: Path,
    source_path: Path,
    offset: int,
    inserted: int,
) -> None:
    payload = {
        "source": str(source_path.resolve()),
        "source_size": source_path.stat().st_size,
        "offset": offset,
        "inserted": inserted,
        "saved_at_unix": time.time(),
    }
    tmp = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, checkpoint_path)


def prepare_doc(raw: dict) -> dict:
    doc = transform_record(raw)

    # Stable identity makes a repeated batch safe after a crash/network error.
    asin = doc.get("parent_asin")
    if asin:
        doc["_id"] = str(asin)

    return doc


def insert_batch_with_retry(
    coll,
    docs: list[dict],
    max_retries: int,
    base_delay: float,
) -> int:
    """Insert one batch safely.

    Because each document has a stable _id, if MongoDB accepted part/all of a
    batch but the client lost the acknowledgement, retrying the same batch only
    produces duplicate-key errors for already committed documents.
    """
    attempt = 0

    while True:
        try:
            coll.insert_many(docs, ordered=False)
            return len(docs)

        except BulkWriteError as exc:
            details = exc.details or {}
            write_errors = details.get("writeErrors", [])
            wc_errors = details.get("writeConcernErrors", [])

            non_duplicates = [
                err for err in write_errors if err.get("code") != 11000
            ]
            if non_duplicates or wc_errors:
                raise

            # All write errors were duplicate _id values. With stable _id values,
            # those documents are already present; after this retry the whole batch
            # is accounted for, so checkpoint progress can safely advance.
            return len(docs)

        except PyMongoError as exc:
            attempt += 1
            if attempt > max_retries:
                raise

            delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
            print(
                f"MongoDB temporary error: {type(exc).__name__}: {exc}\n"
                f"Retrying batch {attempt}/{max_retries} in {delay:.1f}s...",
                flush=True,
            )
            time.sleep(delay)


def ingest(
    path: str,
    uri: str = DEFAULT_URI,
    db_name: str = DB_NAME,
    collection_name: str = COLLECTION_NAME,
    batch_size: int = 1000,
    drop: bool = False,
    resume: bool = False,
    checkpoint: str = "results/ingest_checkpoint.json",
    max_retries: int = 10,
    retry_delay: float = 1.0,
):
    source_path = Path(path)
    checkpoint_path = Path(checkpoint)

    if not source_path.exists():
        raise FileNotFoundError(source_path)

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=30_000,
        connectTimeoutMS=20_000,
        socketTimeoutMS=120_000,
        retryWrites=True,
        appname="amazon-electronics-resumable-ingest",
    )
    coll = client[db_name][collection_name]
    client.admin.command("ping")

    if drop:
        print(f"Dropping {db_name}.{collection_name} ...", flush=True)
        coll.drop()
        if checkpoint_path.exists():
            checkpoint_path.unlink()

    if resume:
        state = load_checkpoint(checkpoint_path, source_path)
        offset = int(state.get("offset", 0))
        inserted_total = int(state.get("inserted", 0))
    else:
        offset = 0
        inserted_total = 0

    print(
        f"Streaming import: batch_size={batch_size}, "
        f"resume={resume}, start_offset={offset:,}",
        flush=True,
    )

    started = time.perf_counter()
    batch: list[dict] = []
    batch_end_offset = offset
    processed_since_start = 0

    # Binary mode gives a reliable byte offset for fast resume.
    with source_path.open("rb") as f:
        f.seek(offset)

        while True:
            raw_line = f.readline()
            if not raw_line:
                break

            current_end = f.tell()
            line = raw_line.strip()
            if not line:
                batch_end_offset = current_end
                continue

            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON near byte offset {current_end}: {exc}"
                ) from exc

            batch.append(prepare_doc(raw))
            batch_end_offset = current_end

            if len(batch) >= batch_size:
                inserted_now = insert_batch_with_retry(
                    coll, batch, max_retries, retry_delay
                )
                inserted_total += inserted_now
                processed_since_start += len(batch)

                save_checkpoint(
                    checkpoint_path,
                    source_path,
                    batch_end_offset,
                    inserted_total,
                )

                if processed_since_start % (batch_size * 10) == 0:
                    print(
                        f"Processed {processed_since_start:,} this run | "
                        f"checkpoint total {inserted_total:,} | "
                        f"offset {batch_end_offset:,}",
                        flush=True,
                    )

                batch = []

        if batch:
            inserted_now = insert_batch_with_retry(
                coll, batch, max_retries, retry_delay
            )
            inserted_total += inserted_now
            processed_since_start += len(batch)
            save_checkpoint(
                checkpoint_path,
                source_path,
                batch_end_offset,
                inserted_total,
            )

    elapsed = time.perf_counter() - started
    final_count = coll.estimated_document_count()

    result = {
        "processed_this_run": processed_since_start,
        "checkpoint_inserted_total": inserted_total,
        "collection_estimated_count": final_count,
        "seconds_this_run": elapsed,
        "records_per_second_this_run": (
            processed_since_start / elapsed if elapsed else None
        ),
        "checkpoint": str(checkpoint_path),
    }
    print(json.dumps(result, indent=2), flush=True)
    client.close()
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--db", default=DB_NAME)
    p.add_argument("--collection", default=COLLECTION_NAME)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--drop", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument(
        "--checkpoint",
        default="results/ingest_checkpoint.json",
    )
    p.add_argument("--max-retries", type=int, default=10)
    p.add_argument("--retry-delay", type=float, default=1.0)
    args = p.parse_args()

    if args.drop and args.resume:
        p.error("--drop and --resume cannot be used together")

    ingest(
        path=args.path,
        uri=args.uri,
        db_name=args.db,
        collection_name=args.collection,
        batch_size=max(1, args.batch_size),
        drop=args.drop,
        resume=args.resume,
        checkpoint=args.checkpoint,
        max_retries=max(0, args.max_retries),
        retry_delay=max(0.1, args.retry_delay),
    )
