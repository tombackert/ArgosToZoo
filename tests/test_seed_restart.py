import os
import signal
import time
import psutil
import pytest

from zoo.argos_env import ArgosEnv

EXPERIMENT = "experiments/footbot_5.argos"

@pytest.mark.timeout(30)
def test_seed_same_does_not_restart(tmp_path):
    env = ArgosEnv(EXPERIMENT, max_steps=2)
    try:
        # First reset with seed A
        env.reset(seed=123)
        pid_first = env.sim_process.pid
        assert psutil.pid_exists(pid_first), "Simulator process missing after first reset"

        # Second reset with SAME seed -> should NOT relaunch, pid unchanged
        env.reset(seed=123)
        pid_second = env.sim_process.pid
        assert pid_first == pid_second, "Simulator restarted unexpectedly for identical seed"

        # Third reset with DIFFERENT seed -> should relaunch (pid changes)
        env.reset(seed=456)
        pid_third = env.sim_process.pid
        assert pid_third != pid_second, "Simulator did not restart on new seed"

    finally:
        env.close()
        # Give a moment for termination
        time.sleep(0.5)
        # Process should be gone or different
        if psutil.pid_exists(pid_first):
            # Try to terminate forcefully (cleanup in CI)
            try:
                os.kill(pid_first, signal.SIGTERM)
            except Exception:
                pass

