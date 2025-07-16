from argos_env import ArgosEnv
import time

if __name__ == "__main__":

    print("Test started...")
    EXPERIMENT = "experiments/footbot_1.argos"
    NUM_AGENTS = 1 

    env = ArgosEnv(argos_file=EXPERIMENT, num_agents=NUM_AGENTS)

    time.sleep(2)
    
    print("\nStarting manual interaction loop...")
    observations, infos = env.reset()
    print(f"Initial observations: {observations}")

    for step in range(100):
        
        actions = {}
        if (step // 5) % 2 == 0:
            actions["robot_1"] = "right_speed"
        else:
            actions["robot_1"] = "left_speed"

        print(f"\n--- Step {step}, Sending actions: {actions} ---")
        observations, _, _, _, _ = env.step(actions)
        print(f"Received observations for robot_0: {observations['robot_0']['proximity'].round(2)}")

        time.sleep(0.1)

    # env.close()
    print("Test finished...")