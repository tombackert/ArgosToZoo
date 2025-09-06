import psutil
import time
import pytest
from zoo.argos_env import ArgosEnv

EXPERIMENT = "experiments/footbot_10.argos"


@pytest.mark.integration
def test_graceful_shutdown_idempotent():
    env = ArgosEnv(argos_file=EXPERIMENT, max_steps=2)
    observations, _ = env.reset(seed=42)
    assert observations
    pid = env.sim_process.pid
    assert psutil.pid_exists(pid), "Simulator process missing before close()"
    env.close()
    # Second close should be no-op
    env.close()
    # Give subprocess time to terminate
    time.sleep(0.5)
    assert not psutil.pid_exists(pid), "Simulator process still alive after close()"
