#!/usr/bin/env python3
"""Random policy driver for ArgosEnv (FUP-13).

Usage:
    PYTHONPATH=src python scripts/random_policy.py \
    --argos experiments/footbot_10.argos --episodes 3 --steps 100 --seed 123

Features:
* Demonstrates PettingZoo parallel API loop with discrete action sampling.
* Aggregates per-episode reward statistics (sum, mean per agent).
* Quiet logging by default (override with --log-level).
* Deterministic when seed provided (env + numpy for action sampling).

Exit code 0 on success; non-zero on uncaught errors.
"""
from __future__ import annotations
import argparse
import numpy as np
from zoo.argos_env import ArgosEnv


def parse_args():
    p = argparse.ArgumentParser(description="Run random policy episodes in ArgosEnv")
    p.add_argument("--argos", required=True, help="Path to .argos experiment file")
    p.add_argument("--episodes", type=int, default=1, help="Number of episodes")
    p.add_argument("--steps", type=int, default=100, help="Max steps per episode")
    p.add_argument("--seed", type=int, default=None, help="Base RNG seed (optional)")
    p.add_argument(
        "--scenario",
        choices=["none", "aggregation"],
        default="none",
        help="Optional scenario to attach a reward callback",
    )
    p.add_argument(
        "--log-level", default="ERROR", help="Python log level (default: ERROR)"
    )
    p.add_argument(
        "--loop-log-level", default="ERROR", help="C++ loop functions log level"
    )
    p.add_argument(
        "--controller-log-level", default="ERROR", help="C++ controller log level"
    )
    return p.parse_args()


def run_episode(env: ArgosEnv, max_steps: int, rng: np.random.Generator):
    # Assumes env.reset() has already been called by caller
    total_reward = {a: 0.0 for a in env.agents}
    for _ in range(max_steps):
        if not env.agents:
            break
        actions = {a: rng.integers(env.action_space(a).n) for a in env.agents}
        obs, rewards, terms, truncs, infos = env.step(actions)
        for a, r in rewards.items():
            total_reward[a] += float(r)
        if all(terms.get(a, False) or truncs.get(a, False) for a in total_reward):
            break
    return total_reward


def main():
    args = parse_args()
    base_seed = args.seed
    rng = np.random.default_rng(base_seed)

    reward_fn = None
    if args.scenario == "aggregation":
        from zoo.scenarios.aggregation import aggregation_reward

        reward_fn = aggregation_reward

    env = ArgosEnv(
        argos_file=args.argos,
        log_level=args.log_level,
        controller_log_level=args.controller_log_level,
        loop_log_level=args.loop_log_level,
        quiet=(args.log_level.upper() == "ERROR"),
        reward_fn=reward_fn,
    )

    try:
        for ep in range(args.episodes):
            ep_seed = None if base_seed is None else int(base_seed + ep)
            obs, info = env.reset(seed=ep_seed)
            rewards = run_episode(env, args.steps, rng)
            mean_per_agent = sum(rewards.values()) / max(len(rewards), 1)
            
            # Debug info for first agent
            print(f"Metrics robot_0: {info['robot_0']}")
            print(
                "Obs robot_0:",
                ", ".join(f"{k}={obs['robot_0'].get(k)}" for k in ("position", "proximity")),
            )
            print(
                f"Episode {ep + 1}/{args.episodes}: total={sum(rewards.values()):.3f} "
                f"mean/agent={mean_per_agent:.3f} agents={len(rewards)}"
            )
    finally:
        env.close()


if __name__ == "__main__":
    main()
