"""Aggregation reward callback (M3-02-RF).

Formula (team reward, broadcast unless per-agent provided):
    r = w_coh * Δcohesion - w_col * max_prox + w_move * moved_mean
Where:
    cohesion_mean = mean distance of agents to centroid (lower is better)
    Δcohesion = prev_cohesion - cohesion_mean (improvement > 0)
    max_prox = max proximity sensor reading across all agents (collision proxy)
    moved_mean = mean translational displacement since previous step
First step after reset => reward forced to 0.0 (baseline suppression).
Success condition (boolean metric only): cohesion_mean < success_threshold for success_hold consecutive steps.

Input data dict (constructed in ArgosEnv.step):
    {
      'step': int,
      'agents': List[str],
      'positions': np.ndarray|None shape (N,3),
      'proximities': Dict[agent, np.ndarray shape (24,)],
      'prev': mutable dict for state caching,
      'first_step': bool
    }
Return tuple: (team_reward: float, per_agent: Optional[Dict[str,float]], metrics: Dict[str,Any])
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional, Tuple


def aggregation_reward(
    data: Dict[str, Any],
    w_coh: float = 1.0,
    w_col: float = 0.5,
    w_move: float = 0.05,
    success_threshold: float = 0.25,
    success_hold: int = 20,
) -> Tuple[float, Optional[Dict[str, float]], Dict[str, Any]]:
    agents = data.get("agents", [])
    positions = data.get("positions")  # np.ndarray or None
    proximities: Dict[str, np.ndarray] = data.get("proximities", {})
    prev: Dict[str, Any] = data.get("prev", {})
    first_step: bool = bool(data.get("first_step", False))

    metrics: Dict[str, Any] = {}

    if positions is None or len(agents) == 0:
        metrics["reward"] = 0.0
        return 0.0, None, metrics

    # Cohesion & centroid
    centroid = positions.mean(axis=0)
    dists = np.linalg.norm(positions[:, :2] - centroid[:2], axis=1)
    cohesion = float(dists.mean())

    prev_coh = prev.get("prev_cohesion")
    delta_coh = 0.0 if prev_coh is None else (prev_coh - cohesion)

    prev_pos = prev.get("prev_positions")
    moved_mean = 0.0
    if (
        prev_pos is not None
        and isinstance(prev_pos, np.ndarray)
        and prev_pos.shape == positions.shape
    ):
        moved_mean = float(
            np.linalg.norm(positions[:, :2] - prev_pos[:, :2], axis=1).mean()
        )

    # Collision proxy
    max_prox = 0.0
    for a in agents:
        prox = proximities.get(a)
        if prox is not None and prox.size:
            val = float(np.max(prox))
            if val > max_prox:
                max_prox = val

    # Success streak
    streak = int(prev.get("success_streak", 0))
    if cohesion < success_threshold:
        streak += 1
    else:
        streak = 0
    success = streak >= success_hold

    if first_step:
        reward = 0.0
    else:
        reward = w_coh * delta_coh - w_col * max_prox + w_move * moved_mean

    # Persist state
    prev["prev_cohesion"] = cohesion
    prev["prev_positions"] = positions.copy()
    prev["success_streak"] = streak

    metrics.update(
        {
            "centroid": centroid.tolist(),
            "cohesion_mean": cohesion,
            "delta_cohesion": float(delta_coh),
            "moved_mean": moved_mean,
            "max_prox": max_prox,
            "success": success,
            "reward": float(reward),
        }
    )
    return float(reward), None, metrics


__all__ = ["aggregation_reward"]
