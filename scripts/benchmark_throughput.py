#!/usr/bin/env python3
"""Throughput / latency benchmark for ArgosToZoo (FUP-09 acceptance).

Measures mean & p95 step latency and payload size for varying agent counts.
Outputs a markdown table + CSV.

Usage:
  PYTHONPATH=src python scripts/benchmark_throughput.py --agents 5 10 --steps 400 --warmup 100
"""
from __future__ import annotations
import argparse
import time
import statistics
from zoo.argos_env import ArgosEnv

EXPERIMENT_TEMPLATE = {
    5: "experiments/footbot_5.argos",  # legacy small scenario
    10: "experiments/footbot_10.argos",
    20: "experiments/footbot_20.argos",
}


def run_case(num_agents: int, steps: int, warmup: int, log_level: str) -> dict:
    exp = EXPERIMENT_TEMPLATE[num_agents]
    env = ArgosEnv(
        exp,
        max_steps=steps + warmup + 10,
        startup_delay=1.0,
        controller_log_level=log_level,
        loop_log_level=log_level,
        log_level="ERROR",
    )
    try:
        env.reset(seed=0)
        # Give simulator one tick before starting timing to avoid initial pending state
        env.step({a: 0 for a in env.agents})
        times = []
        sizes = []
        # warmup
        for _ in range(warmup):
            env.step({a: 0 for a in env.agents})
        for _ in range(steps):
            t0 = time.perf_counter()
            reply_obs, *_ = env.step({a: 0 for a in env.agents})
            dt = (time.perf_counter() - t0) * 1000.0
            times.append(dt)
            # approximate serialized size using proximity arrays only
            sizes.append(sum(o["proximity"].nbytes for o in reply_obs.values()))
        return {
            "agents": num_agents,
            "steps": steps,
            "mean_ms": statistics.mean(times),
            "p95_ms": statistics.quantiles(times, n=100)[94],
            "min_ms": min(times),
            "max_ms": max(times),
            "payload_mean_kb": (statistics.mean(sizes) / 1024.0),
        }
    finally:
        env.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", nargs="+", type=int, required=True)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--warmup", type=int, default=100)
    ap.add_argument("--log-level", default="ERROR")
    # no file output; console only
    args = ap.parse_args()

    results = []
    for n in args.agents:
        if n not in EXPERIMENT_TEMPLATE:
            raise SystemExit(f"No experiment template for {n} agents")
        results.append(run_case(n, args.steps, args.warmup, args.log_level))

    # Determine column widths
    headers = ["agents", "steps", "mean_ms", "p95_ms", "min_ms", "max_ms", "payload_kb"]
    rows = [
        [
            str(r["agents"]),
            str(r["steps"]),
            f"{r['mean_ms']:.2f}",
            f"{r['p95_ms']:.2f}",
            f"{r['min_ms']:.2f}",
            f"{r['max_ms']:.2f}",
            f"{r['payload_mean_kb']:.2f}",
        ]
        for r in results
    ]
    widths = [
        max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)
    ]

    def fmt(row):
        return (
            "| "
            + " | ".join(cell.rjust(widths[i]) for i, cell in enumerate(row))
            + " |"
        )

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    print(sep)
    print(fmt(headers))
    print(sep)
    for row in rows:
        print(fmt(row))
    print(sep)


if __name__ == "__main__":
    main()
