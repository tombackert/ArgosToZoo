import numpy as np
import pytest
from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward

EXPERIMENT = "experiments/footbot_10.argos"


@pytest.mark.integration
def test_reward_variance():
    env = ArgosEnv(EXPERIMENT, max_steps=15, reward_fn=aggregation_reward)
    obs, info = env.reset(seed=123)
    rewards_collected = []
    for _ in range(10):
        # simple repeating action pattern
        actions = {agent: 1 for agent in env.agents}  # forward
        obs, r, term, trunc, info = env.step(actions)
        rewards_collected.extend(r.values())
        if not env.agents:
            break
    env.close()
    arr = np.array(rewards_collected, dtype=float)
    assert arr.size > 0
    # Require some variance (not all identical)
    assert not np.allclose(
        arr, arr[0]
    ), "Rewards appear constant; expected variance > 0."
