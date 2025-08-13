from zoo.argos_env import ArgosEnv
import time

if __name__ == "__main__":
    print("Test started...")
    EXPERIMENT = "experiments/footbot_5.argos"

    # Use a small max_steps first to test truncation behavior
    env = ArgosEnv(argos_file=EXPERIMENT, max_steps=10)
    time.sleep(1.0)

    print("\nStarting interaction loop...")
    observations, infos = env.reset()
    print(f"Discovered agents: {env.agents}")

    # Discrete Actions: 0=stop,1=forward,2=backward,3=turn_left,4=turn_right
    ACTION_PATTERN_A = [1, 3, 4, 0, 2]
    ACTION_PATTERN_B = [2, 4, 3, 0, 1]

    for step in range(10):  # Intentionally exceed max_steps to trigger truncation
        actions = {}
        pattern = ACTION_PATTERN_A if (step // 5) % 2 == 0 else ACTION_PATTERN_B
        for idx, agent in enumerate(env.agents):
            actions[agent] = pattern[idx % len(pattern)]

        print(f"\n--- Step {step} | Actions: {actions} ---")
        observations, _, terminations, truncations, _ = env.step(actions)
        if env.agents:
            first_agent = env.agents[0]
            prox = observations[first_agent]['proximity']
            print(f"Obs[{first_agent}].proximity (len={len(prox)}): {prox[:6].round(2)} ...")
        else:
            # Episode ended due to truncation
            print(f"Episode ended at step={step}. terminations={terminations} truncations={truncations}")
            break
        time.sleep(0.05)

    print("\nLoop finished. Resetting environment...")
    observations, infos = env.reset(options={"max_steps": 3})
    print(f"Discovered agents after reset: {env.agents}")

    env.close()
    print("Test finished.")
    