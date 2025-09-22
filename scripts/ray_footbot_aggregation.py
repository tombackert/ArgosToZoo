import os
import warnings

import torch
import torch.nn as nn

from ray.rllib.models.torch.torch_modelv2 import TorchModelV2
from ray.rllib.models import ModelCatalog
from ray.rllib.utils.torch_utils import FLOAT_MIN

import ray
from ray import tune
from ray.rllib.algorithms.ppo import PPOConfig
from ray.rllib.algorithms.callbacks import DefaultCallbacks
from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
from ray.tune.registry import register_env

from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward


"""
Script to train aggregation with Ray RLlib PPO.


Usage:
PYTHONPATH=src python scripts/ray_footbot_aggregation.py   


Monitor training with:

Run0:
tensorboard --logdir /tmp/ray/session_2025-09-08_15-19-31_320837_42619/artifacts/2025-09-08_15-19-32/PPO_ARGOS_AGGREGATION/driver_artifacts

Run1: 
tensorboard --logdir /tmp/ray/session_2025-09-08_19-13-28_937159_7014/artifacts/2025-09-08_19-13-30/PPO_ARGOS_AGGREGATION/driver_artifacts
"""


# Silence noisy third-party warning unrelated to our code
"""warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pygame.pkgdata",
)
"""

# use GPU
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
torch.set_default_device(DEVICE)

ARGOS_FILE = "experiments/footbot_10.argos"
NUM_AGENTS = 10


class AggMetricsCallbacks(DefaultCallbacks):
    """Aggregate env metrics into RLlib custom_metrics for TensorBoard.

    Expects per-agent infos to contain a 'metrics' dict with keys:
    - 'cohesion_mean', 'delta_cohesion', 'centroid_dir_mean'
    """

    METRIC_KEYS = (
        "cohesion_mean",
        "delta_cohesion",
        "centroid_dir_mean",
        "delta_centroid_dir_mean",
    )

    def on_episode_step(self, *, episode, **kwargs):  # type: ignore[override]
        vals = {k: [] for k in self.METRIC_KEYS}
        for aid in episode.get_agents():
            info = episode.last_info_for(aid)
            if not info:
                continue
            m = info.get("metrics") if isinstance(info, dict) else None
            if not m:
                continue
            for k in self.METRIC_KEYS:
                v = m.get(k)
                if isinstance(v, (int, float)):
                    vals[k].append(float(v))
        for k, arr in vals.items():
            if arr:
                episode.user_data.setdefault(k, []).append(sum(arr) / len(arr))

    def on_episode_end(self, *, episode, **kwargs):  # type: ignore[override]
        for k in self.METRIC_KEYS:
            arr = episode.user_data.get(k, [])
            if arr:
                episode.custom_metrics[k] = float(sum(arr) / len(arr))


def env_creator(env_config):

    argos_file = env_config.get("argos_file", ARGOS_FILE)
    num_agents = env_config.get("expected_num_agents", NUM_AGENTS)

    # Resolve relative path against repo root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if not os.path.isabs(argos_file):
        argos_file = os.path.abspath(os.path.join(repo_root, argos_file))
        if not os.path.exists(argos_file):
            raise FileNotFoundError(f"ARGoS file not found: {argos_file}")

    # Ensure Ray worker CWD matches repo root
    os.chdir(repo_root)

    env = ArgosEnv(
        argos_file=argos_file,
        expected_num_agents=num_agents,
        max_steps=400,
        reward_fn=aggregation_reward,
        quiet=True,
        controller_log_level="ERROR",
        loop_log_level="ERROR",
    )
    return env


if __name__ == "__main__":
    ray.init()

    env_name = "argos_aggregation_v5"
    register_env(env_name, lambda config: ParallelPettingZooEnv(env_creator(config)))

    config = (
        PPOConfig()
        .environment(
            env=env_name,
            env_config={
                "argos_file": ARGOS_FILE,
                "expected_num_agents": NUM_AGENTS,
            },
        )
        .callbacks(AggMetricsCallbacks)
        .evaluation(evaluation_interval=None, evaluation_num_workers=0)
        .env_runners(
            num_env_runners=1,
            rollout_fragment_length=1024,
            create_env_on_local_worker=False,
            batch_mode="truncate_episodes",
        )
        .api_stack(
            enable_rl_module_and_learner=False,
            enable_env_runner_and_connector_v2=False,
        )
        .training(
            train_batch_size=32768,
            lr=2e-4,
            lr_schedule=[
                [0, 3e-4],
                [1_000_000, 2e-4],
                [3_000_000, 1e-4],
            ],
            gamma=0.995,
            lambda_=0.95,
            use_gae=True,
            clip_param=0.2,
            entropy_coeff=0.01,  # More exploration
            entropy_coeff_schedule=[  # Exploration slow decay
                [0, 0.01],
                [1_000_000, 0.005],
                [3_000_000, 0.001],
            ],
            vf_loss_coeff=0.5,
            minibatch_size=1024,
            num_epochs=10,
            model={
                "fcnet_hiddens": [256, 256],
                "vf_share_layers": True,
            },
        )
        .debugging(log_level="ERROR")
        .framework(framework="torch")
        .resources(num_gpus=int(os.environ.get("RLLIB_NUM_GPUS", "0")))
    )

    tune.run(
        "PPO",
        name="PPO_ARGOS_AGGREGATION",
        stop={"timesteps_total": 4_000_000},
        checkpoint_freq=10,
        storage_path="~/ray_results/" + env_name,
        config=config.to_dict(),
        resume=False,
    )
