import functools
import subprocess
import threading
import time
import numpy as np
from pettingzoo import ParallelEnv
from gymnasium.spaces import Box, Dict, Discrete
from zmq_client import ZMQClient
from typing import Optional

class ArgosEnv(ParallelEnv):
    metadata = {"render_modes": ["human"], "name": "argos_v0"}

    def __init__(self, argos_file: str, expected_num_agents: Optional[int] = None, startup_delay: float = 3.0):
        """ARGoS ParallelEnv wrapper.

        Parameters
        ----------
        argos_file : str
            Path to the .argos configuration file.
        expected_num_agents : Optional[int]
            Expected number of agents (validation). If None, no check is performed.
        startup_delay : float
            Time in seconds given to the simulator to start up.
        """
        self.argos_file_path = argos_file
        self._expected_num_agents = expected_num_agents

        # Set after the first reset()
        self.possible_agents = []
        self.agent_name_mapping = {}
        self._agents_initialized = False

        # Start simulator
        self.sim_process = subprocess.Popen(
            ['argos3', '-c', self.argos_file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        threading.Thread(target=self._log_stream, args=(self.sim_process.stdout, "ARGoS-out"), daemon=True).start()
        threading.Thread(target=self._log_stream, args=(self.sim_process.stderr, "ARGoS-err"), daemon=True).start()
        time.sleep(startup_delay)  # Give simulator time to start

        self.client = ZMQClient(port="5555")

        # Public: index -> semantic action; internal -> controller string
        # These strings must match the C++ evaluation.
        self._action_index_to_name = [
            "stop",          # 0
            "forward",       # 1
            "backward",      # 2
            "turn_left",     # 3
            "turn_right"     # 4
        ]
        # Mapping to previously used command strings (compatibility)
        self._action_name_to_command = {
            "stop": "stop",
            "forward": "forward_speed",
            "backward": "backward_speed",
            "turn_left": "left_speed",
            "turn_right": "right_speed",
        }

    def _log_stream(self, stream, prefix):
        for line in iter(stream.readline, ''):
            print(f"[{prefix}] {line.strip()}", flush=True)

    def observation_space(self, agent):
        # 24 proximity sensor values
        return Dict({
            "proximity": Box(low=0, high=1, shape=(24,), dtype=np.float32),
        })

    def action_space(self, agent):
        # Discrete action space according to _action_index_to_name
        return Discrete(len(self._action_index_to_name))

    def reset(self, seed=None, options=None):
        # First reset: derive agents dynamically from simulation
        self.timestep = 0

        reply = self.client.send_command("reset")
        obs_block = reply.get("observations", {})

        if not self._agents_initialized:
            discovered = sorted(list(obs_block.keys()))
            if not discovered:
                raise RuntimeError("No agents found in returned observations.")
            if self._expected_num_agents is not None and self._expected_num_agents != len(discovered):
                raise ValueError(
                    f"Agent count does not match (expected={self._expected_num_agents}, discovered={len(discovered)}, ids={discovered})"
                )
            self.possible_agents = discovered
            self.agent_name_mapping = {name: i for i, name in enumerate(self.possible_agents)}
            self._agents_initialized = True

        self.agents = self.possible_agents[:]

        observations = self._decode_observations(obs_block)
        infos = {agent: {} for agent in self.agents}
        return observations, infos

    def step(self, actions):
        # Expects dict: agent -> int (discrete action) OR agent -> string (fallback)
        if not self.agents:
            raise RuntimeError("No active agents – episode finished or not reset().")

        serialized = {}
        for agent, act in actions.items():
            if agent not in self.agents:
                raise KeyError(f"Unknown agent '{agent}' in actions.")
            command = self._convert_action(act)
            serialized[agent] = command

        payload = {"actions": serialized}
        reply = self.client.send_command("step", payload=payload)

        obs_block = reply.get("observations", {})
        observations = self._decode_observations(obs_block)

        # Placeholder (rewards/terminations to follow in later feature updates)
        rewards = {agent: 0 for agent in self.agents}
        terminations = {agent: False for agent in self.agents}
        truncations = {agent: False for agent in self.agents}
        infos = {agent: {} for agent in self.agents}

        self.timestep += 1
        return observations, rewards, terminations, truncations, infos

    def _decode_observations(self, obs_dict):
        decoded = {}
        for agent, obs in obs_dict.items():
            prox_raw = np.array(obs.get("proximity", []), dtype=np.float32)
            # FUP-03: Validate length (FootBot proximity sensor typically 24 readings)
            if prox_raw.shape != (24,):
                # If length differs, attempt padding/truncation and flag via print (later: logging)
                print(f"[WARN] Proximity vector length {prox_raw.shape} != 24. Auto-adjusting.")
                if prox_raw.size < 24:
                    prox_raw = np.pad(prox_raw, (0, 24 - prox_raw.size), mode='constant', constant_values=0.0)
                else:
                    prox_raw = prox_raw[:24]
            # Normalize to [0,1] if values exceed range (heuristic safeguard)
            if prox_raw.max(initial=0) > 1.0 or prox_raw.min(initial=0) < 0.0:
                max_val = np.max(np.abs(prox_raw))
                if max_val > 0:
                    prox_raw = prox_raw / max_val
            decoded[agent] = {"proximity": prox_raw}
        return decoded

    def validate_observation_spaces(self):
        """Runtime validation to ensure actual observations fit declared spaces.
        Raises AssertionError if mismatch.
        """
        dummy, _ = self.reset()
        for agent, obs in dummy.items():
            space = self.observation_space(agent)
            assert "proximity" in obs, "Missing 'proximity' key in observation"
            prox = obs["proximity"]
            assert prox.shape == (24,), f"Proximity shape mismatch: {prox.shape}" 
            assert (prox >= 0).all() and (prox <= 1).all(), "Proximity values not in [0,1]"
            assert space.contains(obs), "Observation not contained in declared space"
        return True

    def close(self):
        print("Closing ArgosEnv...")
        try:
            self.client.send_command("close")
        except TimeoutError:
            print("Did not receive close confirmation from simulator.")
        
        self.client.close()
        self.sim_process.terminate()
        try:
            self.sim_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.sim_process.kill()

    # ------------------ internal helpers ------------------
    def _convert_action(self, act):
        """Converts discrete index or string into controller command."""
        if isinstance(act, int):
            if act < 0 or act >= len(self._action_index_to_name):
                raise ValueError(f"Action index {act} outside valid range.")
            logical = self._action_index_to_name[act]
        elif isinstance(act, str):
            # Allows both logical names and direct command strings
            if act in self._action_name_to_command:
                logical = act
            else:
                # Check if already one of the final command strings
                if act in self._action_name_to_command.values():
                    return act
                raise ValueError(f"Unknown action string '{act}'.")
        else:
            raise TypeError("Action must be int or str.")

        return self._action_name_to_command[logical]
