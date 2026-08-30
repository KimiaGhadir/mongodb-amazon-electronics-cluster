"""Print Replica Set topology and identify current PRIMARY/SECONDARY nodes."""
from __future__ import annotations

import argparse
import json
import time

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from common import DEFAULT_URI


def status(uri: str):
    client = MongoClient(uri, serverSelectionTimeoutMS=3_000, connectTimeoutMS=3_000)
    try:
        s = client.admin.command("replSetGetStatus")
        members = [
            {
                "name": m["name"],
                "state": m["stateStr"],
                "health": m["health"],
            }
            for m in s["members"]
        ]
        primary = next((m["name"] for m in members if m["state"] == "PRIMARY"), None)
        return {"primary": primary, "members": members}
    finally:
        client.close()


def print_status(uri: str):
    try:
        print(json.dumps(status(uri), indent=2))
    except PyMongoError as exc:
        # During a live election there may briefly be no selectable server.
        print(json.dumps({"temporary_error": str(exc)}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--uri", default=DEFAULT_URI)
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=2.0)
    args = p.parse_args()

    if args.watch:
        try:
            while True:
                print_status(args.uri)
                time.sleep(max(0.2, args.interval))
        except KeyboardInterrupt:
            pass
    else:
        print_status(args.uri)
