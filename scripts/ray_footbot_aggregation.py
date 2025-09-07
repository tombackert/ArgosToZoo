import os
import warnings
import torch
import ray
from ray import tune
from ray.rllib.algorithms.ppo import PPOConfig
from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
from ray.tune.registry import register_env

from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward


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

def env_creator(env_config):

    argos_file = env_config.get("argos_file", "experiments/footbot_10.argos")
    expected = env_config.get("expected_num_agents", 10)

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
        expected_num_agents=expected,
        max_steps=400,
        reward_fn=aggregation_reward,
        quiet=True,
        controller_log_level="ERROR",
        loop_log_level="ERROR",
    )
    return env


if __name__ == "__main__":
    ray.init()

    env_name = "argos_aggregation_v0"
    register_env(env_name, lambda config: ParallelPettingZooEnv(env_creator(config)))

    config = (
        PPOConfig()
        .environment(
            env=env_name,
            env_config={
                "argos_file": "experiments/footbot_10.argos",
                "expected_num_agents": 10,
            },
        )
        .evaluation(evaluation_interval=None, evaluation_num_workers=0)
        .env_runners(
            num_env_runners=2,
            rollout_fragment_length=256,
            create_env_on_local_worker=False,
        )
        .api_stack(
            enable_rl_module_and_learner=False,
            enable_env_runner_and_connector_v2=False,
        )
        .training(
            train_batch_size=8192,  # num_envs * rollout_fragment_length
            lr=3e-4,
            gamma=0.99,
            lambda_=0.95,
            use_gae=True,
            clip_param=0.2,
            entropy_coeff=0.01,  # More exploration
            vf_loss_coeff=0.5,
            minibatch_size=512,
            num_epochs=10,
            model={
                # Standard-FC net for vector obs
                "fcnet_hiddens": [128, 128],
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
        stop={"timesteps_total": 1000000},  # Short training for testing
        checkpoint_freq=10,
        storage_path="~/ray_results/" + env_name,
        config=config.to_dict(),
        resume=False,
    )
