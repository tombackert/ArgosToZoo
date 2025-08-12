from argos_env import ArgosEnv
import time

if __name__ == "__main__":
    print("Test started...")
    EXPERIMENT = "experiments/footbot_5.argos"

    # Automatische Agenten-Discovery (expected_num_agents optional setzen)
    env = ArgosEnv(argos_file=EXPERIMENT, expected_num_agents=None)

    time.sleep(1.0)

    print("\nStarting interaction loop (auto-discovered agents)...")
    observations, infos = env.reset()
    print(f"Discovered agents: {env.agents}")

    ACTION_SET_A = ["forward_speed", "backward_speed", "right_speed", "left_speed"]
    ACTION_SET_B = ["backward_speed", "forward_speed", "left_speed", "right_speed"]

    for step in range(10):
        actions = {}
        chosen = ACTION_SET_A if (step // 5) % 2 == 0 else ACTION_SET_B
        for idx, agent in enumerate(env.agents):
            # Zyklisch Aktionen zuweisen
            actions[agent] = chosen[idx % len(chosen)]

        print(f"\n--- Step {step} | Actions: {actions} ---")
        observations, _, _, _, _ = env.step(actions)
        first_agent = env.agents[0]
        prox = observations[first_agent]['proximity']
        print(f"Obs[{first_agent}].proximity (len={len(prox)}): {prox[:6].round(2)} ...")
        time.sleep(0.05)

    print("\nLoop finished. Resetting environment...")
    observations, infos = env.reset()
    print("Reset successful.")

    # Optional: env.close()
    print("Test finished.")