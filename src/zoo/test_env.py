from argos_env import ArgosEnv
import time

if __name__ == "__main__":
    EXPERIMENT = "experiments/footbot_1.argos"
    NUM_AGENTS = 1 

    env = ArgosEnv(argos_file=EXPERIMENT, num_agents=NUM_AGENTS)
    
    print("\nStarting manual interaction loop...")
    observations, infos = env.reset()
    print(f"Initial observations: {observations}")

    for step in range(100):
        actions = {}
        # Alle 10 Schritte die Aktion ändern
        if (step // 10) % 2 == 0:
            # Die ersten 10, 30, 50... steps
            actions["robot_0"] = "left_speed"
            # actions["robot_1"] = "right_speed"
        else:
            # Die steps 11-20, 31-40...
            actions["robot_0"] = "right_speed"
            #actions["robot_1"] = "left_speed"

        print(f"\n--- Step {step}, Sending actions: {actions} ---")
        observations, _, _, _, _ = env.step(actions)
        print(f"Received observations for robot_0: {observations['robot_0']['proximity'].round(2)}")

        time.sleep(0.1)

    env.close()
    print("Test finished.")