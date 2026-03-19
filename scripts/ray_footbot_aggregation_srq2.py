"""SRQ2 manual baseline training script.

Standalone PPO training for the aggregation task matching marl-platform's
aggregation.py hyperparameters exactly, for a fair efficiency comparison.

Usage:
    PYTHONPATH=src python scripts/ray_footbot_aggregation_srq2.py

Outputs:
    results/aggregation_srq2/tensorboard/   — TensorBoard logs
    results/aggregation_srq2/checkpoints/final/  — final checkpoint
"""

import os
from pathlib import Path

import ray
from ray.rllib.algorithms.ppo import PPOConfig
from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
from ray.tune.registry import register_env
from torch.utils.tensorboard import SummaryWriter

from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward


ARGOS_FILE = "experiments/footbot_aggregation_srq2.argos"
NUM_AGENTS = 10
ITERATIONS = 10
OUTPUT_DIR = "results/aggregation_srq2"


def env_creator(env_config: dict) -> ParallelPettingZooEnv:
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
        max_steps=100,
        reward_fn=aggregation_reward,
        quiet=True,
        controller_log_level="ERROR",
        loop_log_level="ERROR",
    )
    return ParallelPettingZooEnv(env)


if __name__ == "__main__":
    os.environ.setdefault("RAY_DISABLE_MEMORY_MONITOR", "1")
    ray.init()

    env_name = "aggregation_srq2"
    register_env(env_name, env_creator)

    # Resolve output paths relative to repo root
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = repo_root / OUTPUT_DIR
    tensorboard_dir = output_dir / "tensorboard"
    checkpoint_dir = output_dir / "checkpoints" / "final"
    tensorboard_dir.mkdir(parents=True, exist_ok=True)

    print("")
    print("=" * 60)
    print("TENSORBOARD ENABLED")
    print("=" * 60)
    print(f"Log directory: {tensorboard_dir}")
    print("")
    print("To view live training progress, run in a new terminal:")
    print(f"  tensorboard --logdir {tensorboard_dir}")
    print("")
    print("Then open: http://localhost:6006")
    print("=" * 60)
    print("")

    algo_config = (
        PPOConfig()
        .environment(
            env=env_name,
            env_config={
                "argos_file": ARGOS_FILE,
                "expected_num_agents": NUM_AGENTS,
            },
        )
        .api_stack(
            enable_rl_module_and_learner=False,
            enable_env_runner_and_connector_v2=False,
        )
        .framework("torch")
        .env_runners(
            num_env_runners=0,
            rollout_fragment_length="auto",
        )
        .training(
            entropy_coeff=0.01,
            train_batch_size=2000,
            minibatch_size=500,
            num_epochs=10,
        )
        .debugging(log_level="ERROR")
    )

    algo = algo_config.build()
    writer = SummaryWriter(log_dir=str(tensorboard_dir))

    # Training loop
    last_reward = 0.0
    for i in range(ITERATIONS):
        result = algo.train()
        last_reward = (
            result.get("episode_reward_mean")
            or result.get("env_runners", {}).get("episode_reward_mean")
            or result.get("sampler_results", {}).get("episode_reward_mean")
            or 0.0
        )
        print(f"Iteration {i + 1}/{ITERATIONS}  reward_mean={last_reward:.4f}")
        writer.add_scalar("reward/mean", last_reward, i + 1)
        writer.flush()

    # Save checkpoint
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    algo.save(str(checkpoint_dir))
    print(f"\nCheckpoint saved to: {checkpoint_dir}")

    writer.close()
    algo.stop()
    ray.shutdown()
