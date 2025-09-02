import math
from zoo.argos_env import ArgosEnv

MIN_SEP = 0.19  # slightly below configured 0.2 to allow float tolerance


def pairwise_min_dist(positions):
    dmin = 1e9
    for i in range(len(positions)):
        xi, yi, *_ = positions[i]
        for j in range(i + 1, len(positions)):
            xj, yj, *_ = positions[j]
            d = math.hypot(xi - xj, yi - yj)
            if d < dmin:
                dmin = d
    return dmin


def test_seed_layout_determinism():
    env = ArgosEnv("experiments/footbot_10.argos", expected_num_agents=10)
    obs, _ = env.reset(seed=123)
    pos1 = env.get_last_positions()
    env.close()

    env2 = ArgosEnv("experiments/footbot_10.argos", expected_num_agents=10)
    obs2, _ = env2.reset(seed=123)
    pos2 = env2.get_last_positions()
    env2.close()

    assert pos1 is not None and pos2 is not None
    assert pos1 == pos2, "Layouts differ for same seed"
    assert pairwise_min_dist(pos1) >= MIN_SEP, "Min separation violated"
