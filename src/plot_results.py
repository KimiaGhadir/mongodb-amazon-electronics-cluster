"""Generate the two charts required by the assignment from real CSV results."""
from __future__ import annotations

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd


def plot_response_time(csv_path: str, out_dir: str):
    df = pd.read_csv(csv_path)
    if df.empty:
        raise RuntimeError(f"No query benchmark data in {csv_path}")

    pivot = df.pivot_table(index="query", columns="mode", values="avg_ms", aggfunc="mean")
    ax = pivot.plot(kind="bar", figsize=(11, 6))
    ax.set_ylabel("Average response time (ms)")
    ax.set_xlabel("Query")
    ax.set_title("MongoDB query response time - three deployment modes")
    plt.tight_layout()
    path = os.path.join(out_dir, "response_time.png")
    plt.savefig(path, dpi=180)
    plt.close()
    return path


def plot_race_throughput(csv_path: str, out_dir: str):
    df = pd.read_csv(csv_path)
    if df.empty:
        raise RuntimeError(f"No race benchmark data in {csv_path}")

    pivot = df.pivot_table(index="workers", columns="method", values="throughput_req_s", aggfunc="mean")
    ax = pivot.plot(kind="line", marker="o", figsize=(10, 6))
    ax.set_ylabel("Successful update requests / second")
    ax.set_xlabel("Concurrent workers")
    ax.set_title("Concurrent update throughput")
    plt.tight_layout()
    path = os.path.join(out_dir, "race_throughput.png")
    plt.savefig(path, dpi=180)
    plt.close()
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--query-csv", default="results/benchmark.csv")
    p.add_argument("--race-csv", default="results/race_benchmark.csv")
    p.add_argument("--out-dir", default="results/plots")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    outputs = [
        plot_response_time(args.query_csv, args.out_dir),
        plot_race_throughput(args.race_csv, args.out_dir),
    ]
    for path in outputs:
        print(path)
