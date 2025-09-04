#!/usr/bin/env python3
"""RL Compatibility Smoke Test (FUP-15).

Minimal independent multi-agent policy gradient (stateless REINFORCE) to verify
the environment supports a learning signal end-to-end.

Design choices (kept intentionally simple to avoid extra deps):
* Stateless softmax policy per agent (preference vector over discrete actions).
* Ignores observations; objective is to discover higher-return actions
  (e.g. 'forward'). If reward shaping changes, script still validates gradient flow.
* Monte Carlo episode update with discounted returns (gamma) and running
  baseline (exponential moving average) for variance reduction.
* CSV logging of episode reward metrics & selected policy statistics; can be
  plotted externally or inspected quickly.

Limitations:
* Not meant for convergence quality; only smoke validation.
* Ignores observation features; extend to linear policy easily if needed.
* Uses full-episode returns (no bootstrapping) -> higher variance.

Example:
    PYTHONPATH=src python scripts/rl_smoke.py \
    --argos experiments/footbot_10.argos --episodes 20 --steps 50 \
        --seed 123 --csv rl_smoke.csv --gamma 0.95 --lr 0.2

After run inspect rl_smoke.csv or watch stdout for rising forward prob / reward.
"""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path
import numpy as np
from zoo.argos_env import ArgosEnv


def parse_args():
    p = argparse.ArgumentParser(description="RL smoke test (stateless REINFORCE)")
    p.add_argument("--argos", required=True, help="Path to .argos experiment file")
    p.add_argument("--episodes", type=int, default=10, help="Training episodes")
    p.add_argument("--steps", type=int, default=100, help="Max steps per episode")
    p.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    p.add_argument("--lr", type=float, default=0.1, help="Learning rate")
    p.add_argument("--seed", type=int, default=None, help="Base RNG seed")
    p.add_argument(
        "--csv", type=str, default=None, help="Optional CSV output path for metrics"
    )
    p.add_argument(
        "--log-level",
        default="ERROR",
        help="Python log level for environment (default: ERROR)",
    )
    return p.parse_args()


def softmax(x: np.ndarray) -> np.ndarray:
    z = x - np.max(x)
    exp = np.exp(z)
    return exp / np.sum(exp)


def run_episode(
    env: ArgosEnv,
    params: dict[str, np.ndarray],
    rng: np.random.Generator,
    max_steps: int,
):
    # Environment already reset / seeded outside.
    trajectories = {a: {"actions": [], "rewards": []} for a in env.agents}
    for _ in range(max_steps):
        if not env.agents:
            break
        actions = {}
        for a in env.agents:
            prefs = params[a]
            probs = softmax(prefs)
            act = int(rng.choice(len(prefs), p=probs))
            actions[a] = act
            trajectories[a]["actions"].append(act)
        _, rewards, terms, truncs, _ = env.step(actions)
        for a in list(trajectories.keys()):
            trajectories[a]["rewards"].append(float(rewards.get(a, 0.0)))
        if all(terms.get(a, False) or truncs.get(a, False) for a in trajectories):
            break
    return trajectories


def update_policies(
    params: dict[str, np.ndarray],
    trajectories,
    gamma: float,
    lr: float,
    baselines: dict[str, float],
):
    for agent, data in trajectories.items():
        actions = data["actions"]
        rewards = data["rewards"]
        n = len(rewards)
        if n == 0:
            continue
        # Discounted returns G_t
        G = np.zeros(n, dtype=np.float64)
        running = 0.0
        for t in reversed(range(n)):
            running = rewards[t] + gamma * running
            G[t] = running
        # Baseline (EMA of episode mean return)
        ep_return = G[0]
        baselines[agent] = 0.9 * baselines.get(agent, ep_return) + 0.1 * ep_return
        b = baselines[agent]
        prefs = params[agent]
        for t, act in enumerate(actions):
            probs = softmax(prefs)
            advantage = G[t] - b
            # Grad log pi(a_t) for softmax: (one_hot - probs)
            grad = -probs
            grad[act] += 1.0
            prefs += lr * advantage * grad
        # Optional: clip for stability
        np.clip(prefs, -20, 20, out=prefs)
    return baselines


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    env = ArgosEnv(
        argos_file=args.argos,
        log_level=args.log_level,
        quiet=(args.log_level.upper() == "ERROR"),
    )

    csv_fields = [
        "episode",
        "mean_return",
        "total_return",
        "steps",
        "mean_forward_prob",
    ]
    csv_file = None
    writer = None
    if args.csv:
        csv_path = Path(args.csv)
        csv_file = csv_path.open("w", newline="")
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

    try:
        # Seed first episode explicitly for reproducibility if seed provided
        env.reset(seed=args.seed)
        # Initialize policy params after discovering agents
        params = {
            a: np.zeros(env.action_space(a).n, dtype=np.float64) for a in env.agents
        }
        baselines: dict[str, float] = {}

        for ep in range(1, args.episodes + 1):
            # Fresh episode seed sequence (deterministic progression if base seed given)
            ep_seed = None if args.seed is None else args.seed + ep
            env.reset(seed=ep_seed)
            traj = run_episode(env, params, rng, args.steps)
            # Compute metrics
            agent_returns = [sum(t["rewards"]) for t in traj.values()]
            total_ret = float(sum(agent_returns))
            mean_ret = float(np.mean(agent_returns)) if agent_returns else 0.0
            steps_ep = max((len(t["rewards"]) for t in traj.values()), default=0)
            # Policy update
            baselines = update_policies(params, traj, args.gamma, args.lr, baselines)
            # Track forward probability (index 1) mean across agents
            forward_probs = [softmax(params[a])[1] for a in params]
            mean_forward = float(np.mean(forward_probs)) if forward_probs else math.nan
            log_line = (
                f"Ep {ep:03d} | mean_return={mean_ret:.3f} total={total_ret:.3f} "
                f"steps={steps_ep} mean_forward_prob={mean_forward:.3f}"
            )
            print(log_line)
            if writer:
                writer.writerow(
                    {
                        "episode": ep,
                        "mean_return": f"{mean_ret:.6f}",
                        "total_return": f"{total_ret:.6f}",
                        "steps": steps_ep,
                        "mean_forward_prob": f"{mean_forward:.6f}",
                    }
                )
    finally:
        env.close()
        if csv_file:
            csv_file.close()


if __name__ == "__main__":
    main()
