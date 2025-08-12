import functools
import subprocess
import threading
import time
import numpy as np
from pettingzoo import ParallelEnv
from gymnasium.spaces import Box, Dict
from zmq_client import ZMQClient
from typing import Optional

class ArgosEnv(ParallelEnv):
    metadata = {"render_modes": ["human"], "name": "argos_v0"}

    def __init__(self, argos_file: str, expected_num_agents: Optional[int] = None, startup_delay: float = 3.0):
        """ARGoS ParallelEnv Wrapper.

        Parameters
        ----------
        argos_file : str
            Pfad zur .argos Konfigurationsdatei.
        expected_num_agents : Optional[int]
            Erwartete Anzahl Agents (Validierung). Wenn None, keine Prüfung.
        startup_delay : float
            Zeit in Sekunden, die dem Simulator zum Hochfahren gegeben wird.
        """
        self.argos_file_path = argos_file
        self._expected_num_agents = expected_num_agents

        # Wird nach erstem reset() gesetzt
        self.possible_agents = []
        self.agent_name_mapping = {}
        self._agents_initialized = False

        # Simulator starten
        self.sim_process = subprocess.Popen(
            ['argos3', '-c', self.argos_file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        threading.Thread(target=self._log_stream, args=(self.sim_process.stdout, "ARGoS-out"), daemon=True).start()
        threading.Thread(target=self._log_stream, args=(self.sim_process.stderr, "ARGoS-err"), daemon=True).start()
        time.sleep(startup_delay)  # Dem Simulator Zeit zum Starten geben

        self.client = ZMQClient(port="5555")

    def _log_stream(self, stream, prefix):
        for line in iter(stream.readline, ''):
            print(f"[{prefix}] {line.strip()}", flush=True)


    def observation_space(self, agent):
        # 24 Proximity-Sensor-Werte
        return Dict({
            "proximity": Box(low=0, high=1, shape=(24,), dtype=np.float32),
        })


    def action_space(self, agent):
        # Wir definieren hier keine komplexe Action Space, da wir nur Strings senden
        # Für MARL-Algorithmen würde man hier z.B. Discrete(3) für stop/left/right verwenden
        return Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32) # Platzhalter

    def reset(self, seed=None, options=None):
        # Erster Reset: Agenten dynamisch aus Simulation ableiten
        self.timestep = 0

        reply = self.client.send_command("reset")
        obs_block = reply.get("observations", {})

        if not self._agents_initialized:
            discovered = sorted(list(obs_block.keys()))
            if not discovered:
                raise RuntimeError("Keine Agents in den zurückgegebenen Observations gefunden.")
            if self._expected_num_agents is not None and self._expected_num_agents != len(discovered):
                raise ValueError(
                    f"Agentenanzahl stimmt nicht überein (expected={self._expected_num_agents}, discovered={len(discovered)}, ids={discovered})"
                )
            self.possible_agents = discovered
            self.agent_name_mapping = {name: i for i, name in enumerate(self.possible_agents)}
            self._agents_initialized = True

        self.agents = self.possible_agents[:]

        observations = self._decode_observations(obs_block)
        infos = {agent: {} for agent in self.agents}
        return observations, infos

    def step(self, actions):
        # Aktionen an die Loop Function senden
        # 'actions' ist hier ein Dictionary wie z.B. {"robot_0": "left", "robot_1": "stop"}
        serializable_actions = {"actions": actions}
        reply = self.client.send_command("step", payload=serializable_actions)

        observations = self._decode_observations(reply["observations"])
        
        # Platzhalter für Rewards, etc.
        rewards = {agent: 0 for agent in self.agents}
        terminations = {agent: False for agent in self.agents}
        truncations = {agent: False for agent in self.agents}
        infos = {agent: {} for agent in self.agents}

        self.timestep += 1
        return observations, rewards, terminations, truncations, infos

    def _decode_observations(self, obs_dict):
        return {
            agent: {
                "proximity": np.array(obs["proximity"], dtype=np.float32)
            }
            for agent, obs in obs_dict.items()
        }

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