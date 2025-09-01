#!/usr/bin/env python
"""Headless 10-footbot scenario quick launcher with seed override.

Usage:
  python scripts/run_footbot10.py --seed 123 --steps 50

This script instantiates ArgosEnv with the 10-agent headless config and
demonstrates deterministic reset randomization: repeating with the same seed
produces identical first-step positions (queried via internal observation block).
"""
import argparse
from pathlib import Path
from zoo.argos_env import ArgosEnv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=123, help="Environment seed")
    parser.add_argument(
        "--steps", type=int, default=20, help="Number of steps to run (demonstration)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path("experiments/footbot_10.argos")),
        help="Path to .argos config",
    )
    args = parser.parse_args()

    env = ArgosEnv(argos_file=args.config, expected_num_agents=10, max_steps=args.steps)
    obs, _ = env.reset(seed=args.seed)
    print(f"Agents: {list(obs.keys())}")
    positions = env.get_last_positions()
    if positions:
        for agent, pos in zip(obs.keys(), positions):
            if isinstance(pos, (list, tuple)) and len(pos) >= 3:
                x, y, z = pos[:3]
                print(f"  {agent}: position=({x:.3f}, {y:.3f}, {z:.3f})")
            else:
                print(f"  {agent}: position={pos}")
    else:
        print("(No position data available)")
    for t in range(args.steps):
        actions = {agent: 0 for agent in env.agents}  # all stop
        obs, rew, term, trunc, info = env.step(actions)
        if not obs:
            break
    env.close()


if __name__ == "__main__":
    main()
