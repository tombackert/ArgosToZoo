"""Smoke test / manual demo for ArgosEnv.

Converted to be executable by pytest while still runnable as a script.
"""

from zoo.argos_env import ArgosEnv
import pytest
import time
from typing import Dict


EXPERIMENT = "experiments/footbot_5.argos"


def run_demo(max_steps: int = 100, controller_level: str = "INFO", loop_level: str = "INFO"):
    """Run a short interaction loop for manual inspection.

    Matches the following pattern logic: first 5 steps use ACTION_PATTERN_A, next 5 steps ACTION_PATTERN_B
    """
    env = ArgosEnv(
        argos_file=EXPERIMENT,
        max_steps=max_steps,
        startup_delay=1.0,
        controller_log_level=controller_level,
        loop_log_level=loop_level,
    )

    time.sleep(1.0)
    try:
        env.logger.info("Demo started")
        observations, _ = env.reset()
        env.logger.info(f"Discovered agents: {env.agents}")
        ACTION_PATTERN_A = [1, 3, 4, 0, 2]
        ACTION_PATTERN_B = [2, 4, 3, 0, 1]
        for step in range(90):  # intentionally exceed to provoke truncation
            if not env.agents:
                break
            pattern = ACTION_PATTERN_A if (step // 5) % 2 == 0 else ACTION_PATTERN_B
            actions: Dict[str, int] = {
                a: pattern[i % len(pattern)] for i, a in enumerate(env.agents)
            }
            env.logger.info(f"Step {step} actions={actions}")
            observations, _, terminations, truncations, _ = env.step(actions)
            if env.agents:
                first = env.agents[0]
                prox = observations[first]["proximity"]
                env.logger.info(
                    f"Obs[{first}].proximity len={len(prox)} sample={prox[:6].round(2)}"
                )
            time.sleep(0.05)
        env.logger.info("Resetting (max_steps=3)...")
        env.reset(options={"max_steps": 3})
        env.logger.info(f"Agents after reset: {env.agents}")
    finally:
        #env.close()
        try:
            env.logger.info("Demo finished.")
        except Exception:
            pass


@pytest.mark.integration
def test_env_smoke():
    """Pytest: basic run ensures agents, observation shape, truncation."""
    env = ArgosEnv(
        argos_file=EXPERIMENT,
        max_steps=5,
        startup_delay=1.0,
        controller_log_level="ERROR",  # keep test output clean
        loop_log_level="ERROR",
    )
    try:
        obs, _ = env.reset()
        assert env.agents, "No agents discovered"
        first = env.agents[0]
        assert "proximity" in obs[first]
        assert len(obs[first]["proximity"]) == 24
        # Step a few forward actions
        for _ in range(3):
            actions = {a: 1 for a in env.agents}
            obs, _, _, _, _ = env.step(actions)
            if env.agents:
                assert len(obs[first]["proximity"]) == 24
        # Force truncation
        guard = 0
        while env.agents and guard < 10:
            env.step({a: 1 for a in env.agents})
            guard += 1
        assert guard < 10, "Episode failed to truncate"
    finally:
        env.close()


if __name__ == "__main__":  # pragma: no cover
    run_demo(max_steps=100, controller_level="DEBUG", loop_level="DEBUG")
