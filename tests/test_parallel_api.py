"""PettingZoo parallel API conformance test.

Refactored to avoid module-level side effects so that CI can skip gracefully
when the ARGoS binary (argos3) is not installed (fast job scenario).
"""

import shutil
import pytest
from pettingzoo.test import parallel_api_test
from zoo.argos_env import ArgosEnv

EXPERIMENT = "experiments/footbot_5.argos"


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("argos3") is None, reason="argos3 binary missing")
def test_parallel_api():  # noqa: D401
    """Run PettingZoo's parallel_api_test to ensure compliance for ArgosEnv.

    The test is intentionally limited to a small number of cycles because
    underlying ARGoS stepping is comparatively slow vs pure-python envs.
    """
    env = ArgosEnv(argos_file=EXPERIMENT, max_steps=50)
    parallel_api_test(env, num_cycles=1000)
    env.close()
