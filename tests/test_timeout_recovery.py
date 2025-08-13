import pytest
from zoo.argos_env import ArgosEnv

EXPERIMENT = "experiments/footbot_5.argos"


@pytest.mark.timeout(60)
def test_socket_recovery_no_restart():
    """FUP-08: Break client socket and ensure recovery without ARGoS restart.

    Process: reset -> capture PID -> close socket -> step (triggers recovery) -> verify PID stable.
    """
    env = ArgosEnv(argos_file=EXPERIMENT, client_timeout_ms=1000)
    try:
        observations, _ = env.reset(seed=7)
        assert observations, "No observations after reset"
        pid_before = env.sim_process.pid

        # Break socket
        env.client.socket.close(0)

        # Trigger a recovery via direct send_command (empty actions)
        reply = env.client.send_command("step", payload={"actions": {}}, retries=2)
        assert "observations" in reply, "No observations key after recovery"
        assert pid_before == env.sim_process.pid, "Simulator restarted unexpectedly"
    finally:
        env.close()
