import numpy as np
import pytest
from zoo.scenarios.aggregation import aggregation_reward

# Helper to build dummy observations mimicking structure expected from C++ side
# Here we rely on real environment reset/step for integration, but we also
# directly test the internal _compute_metrics for precise control.

EXPERIMENT = "experiments/footbot_10.argos"

# Synthetic positions sets for cohesion math
POSITIONS_CASES = [
    # perfectly overlapping agents -> cohesion 0
    np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
    # triangle roughly radius ~0.816 to centroid (equilateral side 2)
    # -> cohesion_mean ~0.9428? we compute directly
    np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 1.7320508, 0.0]]),
]


def compute_cohesion_mean(positions: np.ndarray) -> float:
    c = positions.mean(axis=0)
    d = np.linalg.norm(positions - c, axis=1)
    return float(d.mean())


def test_cohesion_monotonic_delta():
    # Use direct callback state emulation (no simulator dependency needed for math)
    state_cache = {}

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
    data1 = {
        "step": 0,
        "agents": agents,
        "positions": pos1,
        "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
        "prev": state_cache,
        "first_step": True,
    }
    r1, _, m1 = aggregation_reward(data1)
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
    data2 = {
        "step": 1,
        "agents": agents,
        "positions": pos2,
        "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
        "prev": state_cache,
        "first_step": False,
    }
    r2, _, m2 = aggregation_reward(data2)
    assert m2["cohesion_mean"] < m1["cohesion_mean"]
    assert m2["delta_cohesion"] > 0.0
    assert m2["reward"] > 0.0


def test_success_flag():
    state_cache = {}

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
    metrics = None
    for step in range(4):
        data = {
            "step": step,
            "agents": agents,
            "positions": base,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state_cache,
            "first_step": step == 0,
        }
        _, _, metrics = aggregation_reward(data, success_threshold=0.5, success_hold=3)
    assert metrics is not None and metrics["success"] is True


def test_collision_penalty():
    state_cache = {}

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
    # First step (no reward)
    aggregation_reward(
        {
            "step": 0,
            "agents": agents,
            "positions": positions,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state_cache,
            "first_step": True,
        },
        w_coh=1.0,
        w_col=1.0,
        w_move=0.0,
    )
    # Second step low proximity
    aggregation_reward(
        {
            "step": 1,
            "agents": agents,
            "positions": positions,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state_cache,
            "first_step": False,
        },
        w_coh=1.0,
        w_col=1.0,
        w_move=0.0,
    )
    # Third step high proximity (should reduce reward vs previous improvement path)
    r_high, _, m_high = aggregation_reward(
        {
            "step": 2,
            "agents": agents,
            "positions": positions,
            "proximities": {a: np.full(24, 0.9, dtype=np.float32) for a in agents},
            "prev": state_cache,
            "first_step": False,
        },
        w_coh=1.0,
        w_col=1.0,
        w_move=0.0,
    )
    assert r_high <= 0.0 or m_high["reward"] <= 0.0
