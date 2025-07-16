from argos_env import ArgosEnv
import time

if __name__ == "__main__":

    print("Test started...")
    EXPERIMENT = "experiments/footbot_5.argos"
    NUM_AGENTS = 1 

    env = ArgosEnv(argos_file=EXPERIMENT, num_agents=NUM_AGENTS)

    time.sleep(2)
    
    print("\nStarting manual interaction loop...")
    observations, infos = env.reset()
    print(f"Initial observations: {observations}")

    for step in range(10):
        
        actions = {}
        if (step // 5) % 2 == 0:
            actions["robot_0"] = "forward_speed"
            
            actions["robot_1"] = "backward_speed"

            actions["robot_2"] = "right_speed"

            actions["robot_3"] = "left_speed"
        else:
            actions["robot_0"] = "backward_speed"
            
            actions["robot_1"] = "forward_speed"

            actions["robot_2"] = "left_speed"

            actions["robot_3"] = "right_speed"

        print(f"\n--- Step {step}, Sending actions: {actions} ---")
        observations, _, _, _, _ = env.step(actions)
        print(f"Received observations for robot_0: {observations['robot_0']['proximity'].round(2)}")

        time.sleep(0.1)
    
    print("\nManual interaction loop finished.")
    print("Resetting environment...")
    observations, infos = env.reset()
    


    #env.close()
    print("Test finished...")