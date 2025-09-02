import math
from zoo.argos_env import ArgosEnv


def positions_equal(p1, p2, tol=1e-6):
    if p1 is None or p2 is None or len(p1) != len(p2):
        return False
    for a, b in zip(p1, p2):
        if len(a) < 2 or len(b) < 2:
            return False
        for i in range(2):  # compare x,y only (z constant 0)
            if not math.isclose(a[i], b[i], abs_tol=tol):
                return False
    return True


def test_multiple_runs_same_seed_identical():
    seed = 777
    runs = 3
    layouts = []
    for _ in range(runs):
        env = ArgosEnv("experiments/footbot_10.argos", expected_num_agents=10)
        env.reset(seed=seed)
        layouts.append(env.get_last_positions())
        env.close()
    base = layouts[0]
    for idx, layout in enumerate(layouts[1:], start=1):
        assert positions_equal(
            base, layout
        ), f"Layout {idx} differs for same seed {seed}"


def test_different_seed_yields_different_layout():
    env1 = ArgosEnv("experiments/footbot_10.argos", expected_num_agents=10)
    env1.reset(seed=1001)
    pos1 = env1.get_last_positions()
    env1.close()

    env2 = ArgosEnv("experiments/footbot_10.argos", expected_num_agents=10)
    env2.reset(seed=2002)
    pos2 = env2.get_last_positions()
    env2.close()

    # It is theoretically possible (but astronomically unlikely) to match; guard with assertion
    assert not positions_equal(
        pos1, pos2
    ), "Different seeds produced identical layouts (unexpected)"
