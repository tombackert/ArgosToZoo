import argparse
import os
import time

import ray
from ray.rllib.algorithms.ppo import PPO

from zoo.argos_env import ArgosEnv
from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
from ray.tune.registry import register_env
from zoo.scenarios.aggregation import aggregation_reward


"""
Usage example:

PYTHONPATH=src python scripts/ray_footbot_aggregation_result.py --checkpoint-path ~/ray_results/argos_aggregation_v0/PPO_ARGOS_AGGREGATION/PPO_argos_aggregation_v0_1fc8c_00000_0_2025-09-08_00-15-12/checkpoint_000011 --episodes 1 --sleep 0.02

"""


def env_creator():

    argos_file = "experiments/visual/footbot_10_vis.argos"
    expected_agents = 10

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(repo_root)
    if not os.path.isabs(argos_file):
        argos_file = os.path.abspath(os.path.join(repo_root, argos_file))
    if not os.path.exists(argos_file):
        raise FileNotFoundError(f"ARGoS file not found: {argos_file}")

    env = ArgosEnv(
        argos_file=argos_file,
        expected_num_agents=expected_agents,
        max_steps=400,
        reward_fn=aggregation_reward,          
        quiet=False,
        controller_log_level="WARN",
        loop_log_level="WARN",
    )
    return env


def main():
    parser = argparse.ArgumentParser(description="Render pretrained Argos policy (GUI).")
    parser.add_argument(
        "--checkpoint-path",
        required=True,
        help="Path to RLlib PPO checkpoint (e.g. ~/ray_results/.../checkpoint_000200/checkpoint-200)",
    )
    parser.add_argument(
        "--argos-file",
        default="experiments/visual/footbot_10_vis.argos",
        help="ARGoS config with visualization plugins enabled",
    )
    parser.add_argument("--expected-agents", type=int, default=10)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep per step (sec) to slow down playback")
    args = parser.parse_args()

    checkpoint_path = os.path.expanduser(args.checkpoint_path)

    env = env_creator()
    env_name = "argos_aggregation_v0"
    register_env(env_name, lambda config: ParallelPettingZooEnv(env_creator()))

    ray.init()

    PPOagent = PPO.from_checkpoint(checkpoint_path)

    try:
        for ep in range(args.episodes):
            obs, infos = env.reset()
            done_t = {a: False for a in env.agents}
            done_x = {a: False for a in env.agents}
            ep_reward = 0.0

            while True:
                
                actions = {}
                for a, o in obs.items():
                    if not (done_t.get(a, False) or done_x.get(a, False)):
                       
                        act = PPOagent.compute_single_action(o, policy_id="default_policy", explore=False)
                        actions[a] = act

                obs, rewards, terminations, truncations, infos = env.step(actions)

                # Sum reward 
                if rewards:
                    ep_reward += sum(rewards.values())


                for a, v in terminations.items():
                    done_t[a] = v or done_t.get(a, False)
                for a, v in truncations.items():
                    done_x[a] = v or done_x.get(a, False)

                if all(
                    done_t.get(a, False) or done_x.get(a, False) for a in env.agents
                ):
                    break

                if args.sleep > 0:
                    time.sleep(args.sleep)

            print(f"Episode {ep+1}: return_sum={ep_reward:.3f}")

    finally:
        env.close()
        ray.shutdown()


if __name__ == "__main__":
    main()
