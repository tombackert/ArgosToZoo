from zoo.argos_env import ArgosEnv
import time
from pettingzoo.test import api_test
from pettingzoo.test import parallel_api_test


EXPERIMENT = "experiments/footbot_5.argos"

env = ArgosEnv(argos_file=EXPERIMENT, max_steps=5)
parallel_api_test(env, num_cycles=1000)
env.close()

