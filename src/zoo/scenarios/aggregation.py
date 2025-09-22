"""Simplified Aggregation Reward (position & orientation based only).

New simplified model (per agent i):
    d_t    = || c_t - p_t ||
    d'_t-1 = || c_t - p_{t-1} ||   (current centroid vs previous position)
    u_t    = (c_t - p_t) / max(d_t, eps)
    Δp_t   = p_t - p_{t-1}
    spd    = ||Δp_t||
    If spd > eps:
        h_t    = Δp_t / spd
        cosφ_t = clip(h_t · u_t, [-1,1])
    else cosφ_t = 0.0 (no progress / no measurable reorientation)

    turn_term  = α (cosφ_t - cosφ_{t-1})           (only when moving)
    dist_term  = β (d'_t-1 - d_t)                  (progress toward centroid)
    align_pos  = γ cosφ_t                          (positively reinforce alignment)
    perp_pen   = μ (1 - cosφ_t²)                   (penalize perpendicular movement)

    r_i = turn_term + dist_term + align_pos - perp_pen

Team reward: r_team = mean_i r_i

Persistent states in prev-cache:
    prev_positions : (N,3)
    prev_cos_phi   : (N,)
    agents_signature : Tuple[str,...]

Return signature for compatibility remains:
    (team_reward: float, per_agent: None, metrics: Dict[str,Any])
    per_agent is permanently None (feature removed).

Hyperparameters (Defaults): alpha=0.4, beta=1.0, gamma=0.3, mu=0.2, eps=1e-6

Note: Proximities are currently ignored.
The first step (first_step=True) returns 0.0 and initializes the cache.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
import numpy as np


__all__ = ["aggregation_reward"]


def aggregation_reward(
    data: Dict[str, Any],
    beta: float = 1.0,
    alpha: float = 0.4,
    gamma: float = 0.3,
    mu: float = 0.2,
    eps: float = 1e-6,
) -> Tuple[float, Optional[Dict[str, float]], Dict[str, Any]]:
    """Computes simplified team reward.

    per_agent return is permanently disabled (always None).
    """
    agents = data.get("agents", [])
    positions = data.get("positions")  # (N,3) oder None
    prev: Dict[str, Any] = data.get("prev", {})
    first_step: bool = bool(data.get("first_step", False))

    metrics: Dict[str, Any] = {}
    if positions is None or len(agents) == 0:
        metrics["reward"] = 0.0
        return 0.0, None, metrics

    positions = np.asarray(positions, dtype=float)
    N = positions.shape[0]
    sig = tuple(agents)
    prev_sig = prev.get("agents_signature")
    if prev_sig is not None and prev_sig != sig:
        prev.pop("prev_positions", None)
        prev.pop("prev_cos_phi", None)

    prev_pos = prev.get("prev_positions")
    prev_cos = prev.get("prev_cos_phi")

    centroid = positions.mean(axis=0)
    centroid_xy = centroid[:2]
    delta_c = centroid_xy[None, :] - positions[:, :2]
    d_t = np.linalg.norm(delta_c, axis=1)
    u_t = np.zeros_like(delta_c)
    nz_mask = d_t > eps
    u_t[nz_mask] = delta_c[nz_mask] / d_t[nz_mask, None]

    r_agents = np.zeros(N, dtype=float)
    if (
        first_step
        or prev_pos is None
        or not isinstance(prev_pos, np.ndarray)
        or prev_pos.shape != positions.shape
    ):
        prev["prev_positions"] = positions.copy()
        prev["prev_cos_phi"] = np.zeros(N, dtype=float)
        prev["agents_signature"] = sig
        metrics.update(
            {
                "reward": 0.0,
                "team_reward": 0.0,
                "per_agent_reward": r_agents.tolist(),  # legacy placeholder
                "cohesion_mean": float(d_t.mean()),
                "delta_cohesion": 0.0,
                "moved_mean": 0.0,
                "centroid": centroid.tolist(),
                "centroid_dir_mean": 0.0,
                "delta_centroid_dir_mean": 0.0,
                "turn_term_mean": 0.0,
                "dist_term_mean": 0.0,
                "align_term_mean": 0.0,
                "perp_penalty_mean": 0.0,
                "max_prox": 0.0,
                "success": False,
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "mu": mu,
                "eps": eps,
            }
        )
        return 0.0, None, metrics

    prev_pos = np.asarray(prev_pos, dtype=float)
    delta_p = positions[:, :2] - prev_pos[:, :2]
    spd = np.linalg.norm(delta_p, axis=1)
    d_tm1_prime = np.linalg.norm(centroid_xy[None, :] - prev_pos[:, :2], axis=1)

    if not isinstance(prev_cos, np.ndarray) or prev_cos.shape != (N,):
        prev_cos = np.zeros(N, dtype=float)

    cos_phi_t = prev_cos.copy()
    move_mask = spd > eps
    inst_dir = np.zeros((N, 2), dtype=float)
    inst_dir[move_mask] = delta_p[move_mask] / spd[move_mask, None]
    dots = np.sum(inst_dir * u_t, axis=1)
    dots = np.clip(dots, -1.0, 1.0)
    cos_phi_t[move_mask] = dots[move_mask]

    turn_term = np.zeros(N, dtype=float)
    turn_term[move_mask] = alpha * (cos_phi_t[move_mask] - prev_cos[move_mask])
    dist_term = beta * (d_tm1_prime - d_t)
    align_pos = gamma * cos_phi_t
    perp_pen = mu * (1.0 - cos_phi_t**2)

    r_agents = turn_term + dist_term + align_pos - perp_pen
    team_reward = float(r_agents.mean())

    prev["prev_positions"] = positions.copy()
    prev["prev_cos_phi"] = cos_phi_t.copy()
    prev["agents_signature"] = sig

    metrics.update(
        {
            "reward": team_reward,
            "team_reward": team_reward,
            "per_agent_reward": r_agents.tolist(),  # legacy placeholder
            "turn_term_mean": float(turn_term.mean()),
            "dist_term_mean": float(dist_term.mean()),
            "align_term_mean": float(align_pos.mean()),
            "perp_penalty_mean": float(perp_pen.mean()),
            "mean_cos_phi": float(cos_phi_t.mean()),
            "mean_speed": float(spd.mean()),
            "cohesion_mean": float(d_t.mean()),
            "delta_cohesion": float((d_tm1_prime - d_t).mean()),
            "moved_mean": float(spd.mean()),
            "centroid": centroid.tolist(),
            "centroid_dir_mean": float(dots.mean()),
            "delta_centroid_dir_mean": float((cos_phi_t - prev_cos).mean()),
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "mu": mu,
            "eps": eps,
            "success": False,
        }
    )

    return team_reward, None, metrics
