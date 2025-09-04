import numpy as np
import pytest
from zoo.argos_env import ArgosEnv

# Helper to build dummy observations mimicking structure expected from C++ side
# Here we rely on real environment reset/step for integration, but we also
# directly test the internal _compute_metrics for precise control.

EXPERIMENT = "experiments/footbot_10.argos"

# Synthetic positions sets for cohesion math
POSITIONS_CASES = [
    # perfectly overlapping agents -> cohesion 0
    np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
    # triangle roughly radius ~0.816 to centroid (equilateral side 2) -> cohesion_mean ~0.9428? we compute directly
    np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 1.7320508, 0.0]]),
]


def compute_cohesion_mean(positions: np.ndarray) -> float:
    c = positions.mean(axis=0)
    d = np.linalg.norm(positions - c, axis=1)
    return float(d.mean())


def test_cohesion_monotonic_delta():
    env = ArgosEnv(EXPERIMENT)
    env._prev_cohesion = None
    env._prev_positions_snapshot = None
    env._success_streak = 0
    env._first_reward_step = True

    pos1 = POSITIONS_CASES[1]
    pos2 = pos1 * 0.2
    n = pos1.shape[0]
    agents = [f"robot_{i}" for i in range(n)]
    prox_zero = [[0.0] * 24 for _ in range(n)]

    raw1 = {
        "observations": {
            "schema": "compact_v1",
            "agents": agents,
            "position": pos1.tolist(),
            "proximity": prox_zero,
        }
    }
    m1 = env._compute_metrics(raw1)
    assert pytest.approx(m1["cohesion_mean"]) == compute_cohesion_mean(pos1)
    assert m1["delta_cohesion"] == 0.0
    assert m1["reward"] == 0.0

    raw2 = {
        "observations": {
            "schema": "compact_v1",
            "agents": agents,
            "position": pos2.tolist(),
            "proximity": prox_zero,
        }
    }
    m2 = env._compute_metrics(raw2)
    assert m2["cohesion_mean"] < m1["cohesion_mean"]
    assert m2["delta_cohesion"] > 0.0
    assert m2["reward"] > 0.0


def test_success_flag():
    env = ArgosEnv(EXPERIMENT, success_threshold=0.5, success_hold=3)
    env._prev_cohesion = None
    env._prev_positions_snapshot = None
    env._success_streak = 0
    env._first_reward_step = True

    base = np.array([[0.0, 0.0, 0.0], [0.05, 0.0, 0.0], [0.0, 0.05, 0.0]])
    agents = [f"robot_{i}" for i in range(base.shape[0])]
    prox_zero = [[0.0] * 24 for _ in agents]
    raw = {
        "observations": {
            "schema": "compact_v1",
            "agents": agents,
            "position": base.tolist(),
            "proximity": prox_zero,
        }
    }
    env._compute_metrics(raw)
    metrics = None
    for _ in range(3):
        metrics = env._compute_metrics(raw)
    assert metrics is not None and metrics["success"] is True


def test_collision_penalty():
    env = ArgosEnv(EXPERIMENT, w_coh=1.0, w_col=1.0, w_move=0.0)
    env._prev_cohesion = None
    env._prev_positions_snapshot = None
    env._success_streak = 0
    env._first_reward_step = True

    positions = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    agents = [f"robot_{i}" for i in range(positions.shape[0])]
    prox_low = [[0.0] * 24 for _ in agents]
    prox_high = [[0.9] * 24 for _ in agents]
    raw_low = {
        "observations": {
            "schema": "compact_v1",
            "agents": agents,
            "position": positions.tolist(),
            "proximity": prox_low,
        }
    }
    raw_high = {
        "observations": {
            "schema": "compact_v1",
            "agents": agents,
            "position": positions.tolist(),
            "proximity": prox_high,
        }
    }
    env._compute_metrics(raw_low)
    m_high = env._compute_metrics(raw_high)
    assert m_high["reward"] < 0.0
