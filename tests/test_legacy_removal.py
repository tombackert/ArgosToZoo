import pytest
from zoo.argos_env import ArgosEnv

EXPERIMENT = "experiments/footbot_5.argos"


@pytest.mark.integration
@pytest.mark.parametrize(
    "param,value",
    [
        ("w_coh", 1.0),
        ("w_col", 0.5),
        ("w_move", 0.05),
        ("success_threshold", 0.3),
        ("success_hold", 10),
    ],
)
def test_removed_params_raise(param, value):
    with pytest.raises(TypeError):
        ArgosEnv(EXPERIMENT, **{param: value})


@pytest.mark.integration
def test_no_legacy_internal_state():
    env = ArgosEnv(EXPERIMENT)
    # Ensure legacy attributes are gone
    for name in [
        "_w_coh",
        "_w_col",
        "_w_move",
        "_success_threshold",
        "_success_hold",
        "_prev_cohesion",
        "_success_streak",
        "_prev_positions_snapshot",
        "_first_reward_step",
        "_legacy_compute_aggregation",
        "_compute_metrics",
    ]:
        assert not hasattr(env, name), f"Legacy attribute {name} still present"
    env.close()
