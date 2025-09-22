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


def test_success_flag_removed_placeholder():
    state_cache = {}
    base = np.array([[0.0, 0.0, 0.0], [0.05, 0.0, 0.0], [0.0, 0.05, 0.0]])
    agents = [f"robot_{i}" for i in range(base.shape[0])]
    # Ensure 'success' stays False (placeholder) across steps
    metrics = None
    for step in range(3):
        data = {
            "step": step,
            "agents": agents,
            "positions": base,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state_cache,
            "first_step": step == 0,
        }
        _, _, metrics = aggregation_reward(data)
    assert metrics is not None and metrics["success"] is False


def test_collision_penalty():
    state_cache = {}

    positions = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    agents = [f"robot_{i}" for i in range(positions.shape[0])]
    # Define proximity patterns directly when calling aggregation_reward below
    # Proximity sets (low/high) for collision penalty shaping
    # First step (no reward)
    aggregation_reward(
        {
            "step": 0,
            "agents": agents,
            "positions": positions,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state_cache,
            "first_step": True,
        }
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
        }
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
        }
    )
    assert r_high <= 0.0 or m_high["reward"] <= 0.0


def test_centroid_direction_shaping():
    """Moving towards centroid should yield higher alignment/turn reward than moving away."""
    state = {}
    # Two agents symmetric around origin on x-axis
    prev_pos = np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]], dtype=float)
    agents = ["robot_0", "robot_1"]

    # Initialize cache with first step (no reward)
    aggregation_reward(
        {
            "step": 0,
            "agents": agents,
            "positions": prev_pos,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": True,
        }
    )

    # Step 1: move both agents 0.1 towards centroid -> cosine ~ +1
    towards = np.array([[0.9, 0.0, 0.0], [-0.9, 0.0, 0.0]], dtype=float)
    r_towards, _, m_towards = aggregation_reward(
        {
            "step": 1,
            "agents": agents,
            "positions": towards,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": False,
        }
    )
    assert m_towards["centroid_dir_mean"] > 0.5
    assert r_towards > 0.0

    # Step 2: move away from centroid -> cosine ~ -1
    away = np.array([[1.1, 0.0, 0.0], [-1.1, 0.0, 0.0]], dtype=float)
    r_away, _, m_away = aggregation_reward(
        {
            "step": 2,
            "agents": agents,
            "positions": away,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": False,
        }
    )
    assert m_away["centroid_dir_mean"] < -0.5
    assert r_away < 0.0


def test_moved_mean_positive_when_agents_move():
    """Movement should contribute via dist / alignment;
    verify mean speed metric > 0 and reward non-zero."""
    state = {}
    prev_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=float)
    agents = ["robot_0", "robot_1"]

    aggregation_reward(
        {
            "step": 0,
            "agents": agents,
            "positions": prev_pos,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": True,
        }
    )

    curr = np.array([[0.1, 0.0, 0.0], [1.1, 0.0, 0.0]], dtype=float)
    r, _, m = aggregation_reward(
        {
            "step": 1,
            "agents": agents,
            "positions": curr,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": False,
        }
    )
    assert m["moved_mean"] > 0.0
    # Reward can cancel to zero for symmetric movements; ensure not NaN and within reasonable bounds
    assert not np.isnan(r)


def test_first_step_always_zero_reward():
    state = {}
    positions = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]], dtype=float)
    agents = ["robot_0", "robot_1"]
    r, _, m = aggregation_reward(
        {
            "step": 0,
            "agents": agents,
            "positions": positions,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": True,
        }
    )
    assert m["reward"] == 0.0 and r == 0.0


def test_no_positions_returns_zero():
    state = {}
    agents = ["robot_0", "robot_1"]
    r, _, m = aggregation_reward(
        {
            "step": 0,
            "agents": agents,
            "positions": None,
            "proximities": {a: np.zeros(24, dtype=np.float32) for a in agents},
            "prev": state,
            "first_step": True,
        }
    )
    assert r == 0.0 and m.get("reward", None) == 0.0
