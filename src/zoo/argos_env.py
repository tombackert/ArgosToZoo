import functools
import subprocess
import threading
import time
import numpy as np
import tempfile
import os
import socket
import shutil
import xml.etree.ElementTree as ET
from pettingzoo import ParallelEnv
from gymnasium.spaces import Box, Dict, Discrete  # space Dict
from .zmq_client import ZMQClient
from .logging_utils import get_logger
from typing import Optional, Callable, Any, Tuple, Dict as TDict


class ArgosEnv(ParallelEnv):
    metadata = {"render_modes": ["human"], "name": "argos_v0"}

    def __init__(
        self,
        argos_file: str,
        expected_num_agents: Optional[int] = None,
        startup_delay: float = 3.0,
        max_steps: int = 1000,
        client_timeout_ms: int = 5000,
        log_level: str = "INFO",
        log_format: str = "text",
        quiet: bool = False,
        controller_log_level: Optional[str] = None,
        loop_log_level: Optional[str] = None,
        # Single extensibility mechanism: reward_fn callback.
        reward_fn: Optional[
            Callable[
                [TDict[str, Any]],
                Tuple[float, Optional[TDict[str, float]], TDict[str, Any]],
            ]
        ] = None,
        # Dynamic ZMQ port configuration
        port: Optional[int] = None,
        port_base: int = 5555,
        port_env_vars: Tuple[str, ...] = ("ARGOS_ZMQ_PORT", "ZOO_ZMQ_PORT", "ZMQ_PORT"),
        **kwargs: Any,
    ):
        """ARGoS ParallelEnv wrapper.

        Parameters
        ----------
        argos_file : str
            Path to the .argos configuration file.
        expected_num_agents : Optional[int]
            Expected number of agents (validation).
            If None, no check is performed.
        startup_delay : float
            Time in seconds given to the simulator to start up.
        max_steps : int
            Truncation time limit (episode length).
            Can be overridden per reset via opt "max_steps".
        client_timeout_ms : int
            Timeout for each ZMQ request (ms) before recovery attempts (FUP-08).
        controller_log_level : Optional[str]
            Convenience: if provided sets $ARGOS_CONTROLLER_LOG_LEVEL for the simulator subprocess.
        loop_log_level : Optional[str]
            Convenience: if provided sets $ARGOS_LOOP_LOG_LEVEL for the simulator subprocess.
        """
        # Guard against removed legacy parameters (M3-RM-LEGACY)
        removed = {
            "w_coh",
            "w_col",
            "w_move",
            "success_threshold",
            "success_hold",
        }
        unexpected = removed.intersection(kwargs.keys())
        if unexpected:
            raise TypeError(
                "Removed legacy aggregation parameters passed: "
                f"{sorted(unexpected)}. Provide reward_fn (see scenarios/aggregation) instead."
            )

        effective_level = "ERROR" if quiet else log_level
        self.logger = get_logger(effective_level, log_format)

        # Core config
        self.argos_file_path = os.path.abspath(argos_file)
        # Always work with absolute path (Ray workers may change CWD)
        self._active_config_path = self.argos_file_path
        if not os.path.exists(self._active_config_path):
            raise FileNotFoundError(
                f"ARGoS config not found: {self._active_config_path}"
            )
        self._expected_num_agents = expected_num_agents
        self._max_steps = int(max_steps)
        self.timestep = 0
        self._current_seed = None  # type: Optional[int]
        self.np_random = None
        self._client_timeout_ms = client_timeout_ms
        self._closed = False  # Graceful shutdown state flag
        self._log_threads = []  # list[threading.Thread]
        self._last_return_code = None  # type: Optional[int]
        self._shutting_down = False
        self._last_positions = (
            None  # positions from latest raw reply (list[list[float]])
        )
        # Dynamic port selection
        self._port_env_vars = tuple(port_env_vars)
        self._port_base = int(os.environ.get("ARGOS_ZMQ_PORT_BASE", str(port_base)))
        self._port = (
            int(port) if port is not None else self._pick_free_port(self._port_base)
        )

        # Agent discovery state
        self.possible_agents = []  # list[str]
        self.agent_name_mapping = {}  # dict[str,int]
        self._agents_initialized = False

        # Desired C++ log levels (propagated to subprocess env)
        self._controller_log_level = controller_log_level
        self._loop_log_level = loop_log_level
        # Optional compact batched observation schema (FUP-09 optimization)
        # Unified compact observation schema always enabled (FUP-09 consolidation)

        # Simulator startup
        self._startup_delay = startup_delay
        # Optionally write a temp config with injected port attributes (best effort)
        self._active_config_path = self._create_temp_config_with_port(
            self._active_config_path, self._port
        )
        self._launch_simulator()
        self.logger.debug("Simulator launched", config=self._active_config_path)

        # Action mapping (discrete -> controller command)
        self._action_index_to_name = [
            "stop",
            "forward",
            "backward",
            "turn_left",
            "turn_right",
        ]
        self._action_name_to_command = {
            "stop": "stop",
            "forward": "forward_speed",
            "backward": "backward_speed",
            "turn_left": "left_speed",
            "turn_right": "right_speed",
        }
        # Reward callback (single path) and generic per-episode mutable state cache
        self._reward_fn = reward_fn
        self._reward_state: TDict[str, Any] = {}

    def _log_stream(self, stream, prefix):
        for line in iter(stream.readline, ""):
            print(f"[{prefix}] {line.strip()}", flush=True)

    @functools.lru_cache(maxsize=None)
    def observation_space(self, agent):
        # 24 proximity sensor values
        return Dict(
            {
                "position": Box(low=-np.inf, high=np.inf, shape=(3,), dtype=np.float32),
                "proximity": Box(low=0, high=1, shape=(24,), dtype=np.float32),
            }
        )

    @functools.lru_cache(maxsize=None)
    def action_space(self, agent):
        # Discrete action space according to _action_index_to_name
        return Discrete(len(self._action_index_to_name))

    def reset(self, seed=None, options=None):
        # Reset episode counters
        self.timestep = 0
        # Reset reward state cache (external callback may store persistent values here)
        self._reward_state.clear()
        if options and "max_steps" in options:
            self._max_steps = int(options["max_steps"])

        # Seeding: ALWAYS restart underlying simulator if a seed is provided
        if seed is not None:
            self._apply_seed_and_restart(seed)

        reply = self.client.send_command("reset")
        obs_block = reply.get("observations", {})
        if isinstance(obs_block, dict) and obs_block.get("schema") == "compact_v1":
            self._last_positions = obs_block.get("position", [])

        if not self._agents_initialized:
            if isinstance(obs_block, dict) and obs_block.get("schema") == "compact_v1":
                discovered = list(obs_block.get("agents", []))
            else:
                discovered = sorted(list(obs_block.keys()))
            if not discovered:
                raise RuntimeError("No agents found in returned observations.")
            if (
                self._expected_num_agents is not None
                and self._expected_num_agents != len(discovered)
            ):
                raise ValueError(
                    "Agent count does not match (expected="
                    f"{self._expected_num_agents}, discovered={len(discovered)},"
                    f" ids={discovered})"
                )
            self.possible_agents = discovered
            self.agent_name_mapping = {
                name: i for i, name in enumerate(self.possible_agents)
            }
            self._agents_initialized = True

        self.agents = self.possible_agents[:]
        observations = self._decode_observations(obs_block)
        metrics = {"reward": 0.0}
        infos = {agent: {"metrics": metrics} for agent in self.agents}
        return observations, infos

    def step(self, actions):
        # If episode finished, comply with ParallelEnv: empty structures
        if not self.agents:
            if actions:
                raise RuntimeError(
                    "Environment is done; provide empty action dict or reset()."
                )
            return {}, {}, {}, {}, {}

        # Serialize and validate actions
        serialized: dict[str, str] = {}
        for agent, act in actions.items():
            if agent not in self.agents:
                raise KeyError(f"Unknown agent '{agent}' in actions.")
            serialized[agent] = self._convert_action(act)

        # Sync request (actions applied next tick, observations are post-step)
        reply = self.client.send_command("step", payload={"actions": serialized})
        obs_block = reply.get("observations", {})
        if isinstance(obs_block, dict) and obs_block.get("schema") == "compact_v1":
            self._last_positions = obs_block.get("position", [])
        observations = self._decode_observations(obs_block)

        metrics: TDict[str, Any] = {}
        team_reward = 0.0
        per_agent: Optional[TDict[str, float]] = None
        if self._reward_fn is not None:
            # Build data package for callback
            obs_block = reply.get("observations", {}) if isinstance(reply, dict) else {}
            positions = None
            if isinstance(obs_block, dict) and obs_block.get("schema") == "compact_v1":
                pos_list = obs_block.get("position", [])
                if pos_list:
                    positions = np.array(pos_list, dtype=np.float32)
            proximities = {a: od["proximity"] for a, od in observations.items()}
            data = {
                "step": self.timestep,
                "agents": list(self.agents),
                "positions": positions,
                "proximities": proximities,
                "prev": self._reward_state,  # mutable cache
                "first_step": self.timestep == 0,
            }
            try:
                team_reward, per_agent, metrics = self._reward_fn(data)
            except Exception as e:
                self.logger.warn("reward_fn_error", error=str(e))
                team_reward, per_agent, metrics = 0.0, None, {}
        else:
            metrics = {"reward": 0.0}
            team_reward = 0.0
        if per_agent is None:
            rewards = {agent: float(team_reward) for agent in self.agents}
        else:
            rewards = {
                agent: float(per_agent.get(agent, team_reward)) for agent in self.agents
            }
        terminations = {agent: False for agent in self.agents}
        truncations = {agent: False for agent in self.agents}
        infos = {agent: {"metrics": metrics} for agent in self.agents}

        self.timestep += 1
        if self.timestep >= self._max_steps:
            truncations = {agent: True for agent in self.agents}
            out = (observations, rewards, terminations, truncations, infos)
            self.agents = []
            return out

        return observations, rewards, terminations, truncations, infos

    def _decode_observations(self, obs_dict):
        """Decode observations coming from the C++ side.

            Supports two wire formats:
            1. Legacy (default): {agent_id: {"proximity": [...], "position": [...]}, ...}
        2. Unified compact schema (always used):
               {
                 "schema": "compact_v1",
                 "agents": ["robot_0", ...],
                 "proximity": [[...24...], ...],
                 "position": [[x,y,z], ...]
               }
            Both forms are converted into a uniform per-agent dict only including
            the "proximity" key (position currently unused in Python wrapper but
            retained for future reward shaping / observations extensions).
        """
        # Compact schema envelope (always expected)
        if isinstance(obs_dict, dict) and obs_dict.get("schema") == "compact_v1":
            agents = obs_dict.get("agents", [])
            proximities = obs_dict.get("proximity", [])
            positions = obs_dict.get("position", [])
            rebuilt: dict[str, dict] = {}
            for idx, agent in enumerate(agents):
                prox_raw = np.array(
                    proximities[idx] if idx < len(proximities) else [],
                    dtype=np.float32,
                )
                pos_raw = np.array(
                    positions[idx] if idx < len(positions) else [],
                    dtype=np.float32,
                )
                rebuilt[agent] = {"position": pos_raw, "proximity": prox_raw}
            obs_dict = rebuilt  # normalized legacy-like dict

        decoded = {}
        for agent, obs in obs_dict.items():
            prox_raw = np.array(obs.get("proximity", []), dtype=np.float32)
            pos_raw = np.array(obs.get("position", []), dtype=np.float32)

            if prox_raw.shape != (24,):
                # Length differs: pad/truncate and flag (later: logging)
                self.logger.warn(
                    "Proximity length mismatch; auto-adjust", length=int(prox_raw.size)
                )
                if prox_raw.size < 24:
                    prox_raw = np.pad(
                        prox_raw,
                        (0, 24 - prox_raw.size),
                        mode="constant",
                        constant_values=0.0,
                    )
                else:
                    prox_raw = prox_raw[:24]
            # Normalize to [0,1] if values exceed range (heuristic safeguard)
            if prox_raw.max(initial=0) > 1.0 or prox_raw.min(initial=0) < 0.0:
                max_val = np.max(np.abs(prox_raw))
                if max_val > 0:
                    prox_raw = prox_raw / max_val

            # Position: enforce length 3 (pad/truncate)
            if pos_raw.shape != (3,):
                if pos_raw.size < 3:
                    pos_raw = np.pad(
                        pos_raw,
                        (0, 3 - pos_raw.size),
                        mode="constant",
                        constant_values=0.0,
                    )
                else:
                    pos_raw = pos_raw[:3]

            decoded[agent] = {"position": pos_raw, "proximity": prox_raw}
        return decoded

    def validate_observation_spaces(self):
        """Runtime validation to ensure actual observations fit declared spaces.
        Raises AssertionError if mismatch.
        """
        dummy, _ = self.reset()
        for agent, obs in dummy.items():
            space = self.observation_space(agent)
            assert "position" in obs, "Missing 'position' key in observation"
            pos = obs["position"]
            assert pos.shape == (3,), f"Position shape mismatch: {pos.shape}"
            assert "proximity" in obs, "Missing 'proximity' key in observation"
            prox = obs["proximity"]
            assert prox.shape == (24,), f"Proximity shape mismatch: {prox.shape}"
            assert (prox >= 0).all() and (
                prox <= 1
            ).all(), "Proximity values not in [0,1]"
            assert space.contains(obs), "Observation not contained in declared space"
        return True

    def close(self):
        """Gracefully release all external resources.

        Idempotent: multiple invocations are safe (FUP-12).
        Ensures simulator process is terminated and log threads joined.
        """
        if self._closed:
            return
        self.logger.info("Closing ArgosEnv")
        self._shutdown_simulator()
        # Attempt to join log threads briefly (non-blocking overall)
        for t in self._log_threads:
            if t.is_alive():
                t.join(timeout=0.5)
        self._closed = True

    # ------------------ inspection helpers ------------------
    def get_last_positions(self):
        """Return last recorded raw positions array (list of [x,y,z]) or None.

        Useful for verifying deterministic placement across seeded resets.
        """
        return self._last_positions

    # ------------------ internal helpers ------------------
    def _convert_action(self, act):
        """Converts discrete index or string into controller command."""
        # Accept native ints and numpy integer scalar types
        if isinstance(act, (int, np.integer)):
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

    # ------------------ seeding & process management ------------------
    def _launch_simulator(self):
        # Propagate current process env and add optional log level overrides
        env = os.environ.copy()
        if self._controller_log_level:
            env["ARGOS_CONTROLLER_LOG_LEVEL"] = self._controller_log_level
        if self._loop_log_level:
            env["ARGOS_LOOP_LOG_LEVEL"] = self._loop_log_level
        # Export chosen ZMQ port for C++ side to consume
        for k in self._port_env_vars:
            env[k] = str(self._port)
        # No feature flag needed: compact schema is standard
        self.sim_process = subprocess.Popen(
            ["argos3", "-c", self._active_config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        # Spawn and track log threads so we can join them on close
        out_thread = threading.Thread(
            target=self._log_stream,
            args=(self.sim_process.stdout, "ARGoS-out"),
            daemon=True,
        )
        err_thread = threading.Thread(
            target=self._log_stream,
            args=(self.sim_process.stderr, "ARGoS-err"),
            daemon=True,
        )
        out_thread.start()
        err_thread.start()
        self._log_threads = [out_thread, err_thread]
        self._closed = False
        time.sleep(self._startup_delay)
        # Recreate client (new ZMQ server instance in simulator)
        self.client = ZMQClient(
            port=str(self._port), timeout_ms=self._client_timeout_ms
        )

    def _shutdown_simulator(self):
        # Prevent re-entrancy issues if already closed
        if hasattr(self, "_shutting_down") and self._shutting_down:
            return
        self._shutting_down = True
        if hasattr(self, "client") and self.client:
            try:
                self.client.send_command("close")
            except Exception:
                pass
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        if hasattr(self, "sim_process") and self.sim_process:
            if self.sim_process.poll() is None:
                self.sim_process.terminate()
                try:
                    self.sim_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.sim_process.kill()
            # Capture return code for diagnostics
            self._last_return_code = self.sim_process.returncode
            # Close pipes explicitly (threads will exit when EOF)
            try:
                if self.sim_process.stdout:
                    self.sim_process.stdout.close()
                if self.sim_process.stderr:
                    self.sim_process.stderr.close()
            except Exception:
                pass
            self.sim_process = None
        self._shutting_down = False

    def _apply_seed_and_restart(self, seed: int):
        """Generate a temporary ARGoS config with the given seed then restart.

        ARGoS sets its RNG seed at experiment initialization; to guarantee
        reproducibility we must restart the process when a new seed is
        requested.
        """
        self._current_seed = int(seed)
        self.np_random = np.random.default_rng(self._current_seed)
        # Create seeded config file
        try:
            tree = ET.parse(self.argos_file_path)
            root = tree.getroot()
            # Find <experiment> node anywhere
            exp_node = root.find(".//experiment")
            if exp_node is None:
                self.logger.warn("No <experiment> node; cannot set random_seed")
            else:
                exp_node.set("random_seed", str(self._current_seed))
            # Write to temp file
            fd, tmp_path = tempfile.mkstemp(
                prefix=f"argos_seed_{self._current_seed}_", suffix=".argos"
            )
            os.close(fd)
            tree.write(tmp_path)
            # Also ensure the current port is reflected in the temp config
            self._active_config_path = self._create_temp_config_with_port(
                tmp_path, self._port
            )
        except Exception as e:
            self.logger.warn(
                "Failed to create seeded config; using original", error=str(e)
            )
            self._active_config_path = self.argos_file_path
        # Restart simulator
        self._shutdown_simulator()
        self._launch_simulator()

    # ------------------ Port helpers ------------------
    def _pick_free_port(self, start: int) -> int:
        """Selects an available TCP port.

        Prefers OS-assigned ephemeral ports; falls back to linear probing from `start`.
        """
        # Try OS ephemeral port
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                return s.getsockname()[1]
        except Exception:
            pass
        # Fallback: probe from start
        for p in range(start, start + 2000):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", p))
                    return p
                except OSError:
                    continue
        raise RuntimeError("No free TCP port found for ZMQ")

    def _create_temp_config_with_port(self, src_path: str, port: int) -> str:
        """Copy src .argos to a temp file and attempt to set any plausible ZMQ port attrs to `port`.

        If nothing is changed (no matching attributes), returns the copy path anyway.
        """
        # Make a temp copy first
        fd, tmp_path = tempfile.mkstemp(prefix="argos_cfg_", suffix=".argos")
        os.close(fd)
        shutil.copyfile(src_path, tmp_path)
        try:
            tree = ET.parse(tmp_path)
            root = tree.getroot()
            changed = False
            cand_attrs = ("port", "zmq_port", "server_port", "rpc_port", "ipc_port")
            for elem in root.iter():
                for attr in cand_attrs:
                    if attr in elem.attrib:
                        try:
                            int(elem.attrib[attr])  # numeric-like
                            elem.set(attr, str(port))
                            changed = True
                        except Exception:
                            continue
            if changed:
                tree.write(tmp_path)
        except Exception:
            # Keep the copy; C++ may read port from env
            pass
        return tmp_path
