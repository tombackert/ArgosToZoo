#!/usr/bin/env python3
"""Manual keyboard control using ArgosEnv (PettingZoo) instead of raw ZMQ.

Usage:
  PYTHONPATH=src python scripts/manual_control.py --argos experiments/visual/footbot_10_vis.argos \
    --scenario none|aggregation --seed 0
"""
from __future__ import annotations
import argparse
from zoo.argos_env import ArgosEnv


def parse_args():
    p = argparse.ArgumentParser(description="Manual control via ArgosEnv")
    p.add_argument("--argos", required=True, help="Path to .argos experiment file")
    p.add_argument("--seed", type=int, default=None, help="Optional env seed")
    p.add_argument(
        "--scenario",
        choices=["none", "aggregation"],
        default="none",
        help="Optional scenario to attach a reward callback",
    )
    p.add_argument("--log-level", default="ERROR")
    p.add_argument("--loop-log-level", default="ERROR")
    p.add_argument("--controller-log-level", default="ERROR")
    return p.parse_args()


def main():
    args = parse_args()
    reward_fn = None
    if args.scenario == "aggregation":
        from zoo.scenarios.aggregation import aggregation_reward

        reward_fn = aggregation_reward

    env = ArgosEnv(
        argos_file=args.argos,
        log_level=args.log_level,
        loop_log_level=args.loop_log_level,
        controller_log_level=args.controller_log_level,
        reward_fn=reward_fn,
        quiet=(args.log_level.upper() == "DEBUG"),
    )

    try:
        env.reset(seed=args.seed)
        print("Controls: w/a/s/d for forward/left/back/right, 'x' stop, 'q' quit")
        key_to_action = {
            "x": "stop",
            "w": "forward",
            "s": "backward",
            "a": "turn_left",
            "d": "turn_right",
        }
        while True:
            cmd = input("Command (w/a/s/d/x/q): ").strip().lower()
            if cmd == "q":
                break
            if cmd not in key_to_action:
                print("Unknown command.")
                continue
            # Map to discrete index via env helper mapping
            logical = key_to_action[cmd]
            # Convert logical to final controller command via env internal mapping
            # Here we send per-agent the logical command string, env._convert_action accepts strings
            actions = {a: logical for a in env.agents}
            obs, rewards, terms, truncs, infos = env.step(actions)
            # Summarize feedback
            rsum = sum(float(r) for r in rewards.values()) if rewards else 0.0
            print(f"step done: total_reward={rsum:.3f}")
            if not obs:
                print("Episode finished (truncate/terminate). Resetting...")
                env.reset(seed=args.seed)
    finally:
        env.close()


if __name__ == "__main__":
    main()
