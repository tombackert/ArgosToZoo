[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md) | [Results](results.md) | [Backlog](backlog.md)

# Architecture: ARGoS-PettingZoo Bridge

This document describes the technical architecture that enables communication between the C++-based ARGoS simulator and an external Python control script.

## Component Overview

The system consists of two decoupled main components connected via inter-process communication (IPC):

1. **ARGoS Simulator (Server Side):**
   * **Language:** C++
   * **Role:** Serves as the simulation environment, handling physical simulation, sensor data generation, and execution of actuator commands.
   * **Core:** A custom **controller plugin** (`my_ipc_controller`), compiled as a dynamic library (`.dylib`). Each simulated robot receives an instance of this controller.

2. **Python Control (Client Side):**
   * **Language:** Python
   * **Role:** Acts as the "brain" of the robots. It implements decision logic (manually or later via a MARL algorithm) and sends control commands to the simulator.
   * **Core:** A Python script (`manual_control.py`) that establishes the connection to the controllers in the simulator.

## Communication Bridge

Communication between the two processes is implemented using a carefully selected technology stack.

* **Messaging Library: ZeroMQ (ØMQ)**
  * ZeroMQ is used as a lightweight, high-performance messaging layer that abstracts network programming complexity.
  * It enables seamless communication between different programming languages (C++ and Python) without a central message broker.

* **Communication Pattern: Request-Reply (REQ/REP)**
  * The system uses ZeroMQ’s REQ/REP pattern, enforcing a strict synchronous message exchange.
  * **Python Client (REQ Socket):** Sends a request (control command) and waits for a reply.
  * **C++ Controller (REP Socket):** Waits for a request, processes it, and sends a reply (status/sensor data).
  * This pattern ensures each command is acknowledged, simplifying the logic.

* **Data Format: JSON**
  * All messages between C++ and Python are exchanged as JSON-formatted strings.
  * JSON was chosen for its readability and excellent parser support in both languages, easing development and debugging.

## Multi-Agent Scaling

The system adopts a **centralized single-socket design (Option A of FUP-09)** for multi-agent scaling. Instead of one ZeroMQ port per robot, a single REP socket (default: `tcp://*:5555`) serves batched requests containing all agent actions and returns batched observations. This approach was chosen for its lower connection management overhead, simpler recovery semantics, and better scalability under moderate agent counts (<100) typical for early-stage MARL prototyping.

Key aspects:

1. **Central REP Socket:** Implemented in `zoo_loop_functions.cpp`; all agent actions are applied in `PreStep()`, and a single response with all raw observations (no rewards) is sent in `PostStep()`. Reward & metrics logic now lives purely in Python.
2. **Agent Indexing:** Agents are deterministically named `robot_0..robot_{N-1}` in discovery order. Python infers the set after the first reset.
3. **Batch Payloads:** Request JSON: `{ "command": "step", "payload": { "actions": { "robot_0": "forward_speed", ... }}}`. Response JSON contains an `observations` object.
4. **Unified Observation Schema:** The C++ layer emits a compact batched envelope with only task‑agnostic data:
   ```json
   {
     "observations": {
       "schema": "compact_v1",
       "agents": ["robot_0", "robot_1"],
       "proximity": [[...24 floats...], [...]],
  "position": [[x,y,z], [...]]
     }
   }
   ```
   This minimizes repeated keys and lowers serialization overhead. A developer utility (future work) can pretty‑print this into per‑agent dictionaries for manual debugging without changing the wire protocol.
5. **Extensibility:** Additional sensors append new parallel arrays (e.g., `light`, `battery`) and increment the schema version only if breaking changes are introduced.

## Control Flow

The typical control flow for a simulation step is as follows:

1. The ARGoS simulator runs and calls the loop functions `PreStep()` and `PostStep()` each tick.
2. `PostStep()` collects observations (no reward computation) and blocks waiting for the next batched request from Python (REQ/REP ensures sync).
3. The Python `ArgosEnv.step()` sends one JSON request with all agent actions.
4. `PreStep()` applies the newly received actions to each controller before physics advancement.
5. The cycle repeats, guaranteeing exactly one simulation tick per Python step, aiding determinism and seed reproducibility.

## Project Structure

The repository is organized into the following directories:

```
.
├── CMakeLists.txt              # Main CMake configuration for the C++ plugin
├── README.md                   # Project overview, setup, and usage instructions
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── build/                      # Compiled C++ binaries and build artifacts (auto-generated)
├── docs/                       # Documentation, diagrams, and architectural notes
│   ├── architecture.md         # This file
│   ├── concept.md              # High-level project concept
│   ├── how-to-run.md           # Detailed setup and execution guide
│   ├── logging.md              # Logging configuration and usage
│   ├── tests.md                # Testing documentation
│   ├── resources.md            # External resources and references
│   ├── project-management.md   # Project management notes
│   ├── results.md              # Experimental results
│   └── backlog.md              # Future work and backlog items
├── experiments/                # ARGoS configuration files (.argos) for different scenarios
│   ├── footbot_1.argos         # Scenario with one robot
│   ├── footbot_5.argos         # Scenario with five robots
│   ├── footbot_10.argos        # Headless aggregation scenario with ten robots
│   ├── footbot_20.argos        # Scenario with twenty robots
│   ├── zmq.argos               # ZeroMQ experiment configuration
│   └── visual/                 # Visual experiment configurations
│       ├── footbot_1_vis.argos
│       ├── footbot_5_vis.argos
│       ├── footbot_10_vis.argos
│       └── footbot_20_vis.argos
├── scripts/                    # Standalone Python scripts for control, training, and interaction
│   ├── manual_control.py       # Script for manually controlling robots via the terminal
│   ├── random_policy.py        # Random policy driver for sanity checks
│   ├── rl_smoke.py             # Minimal REINFORCE smoke test for RL compatibility
│   ├── benchmark_throughput.py # Performance benchmarking script
│   ├── run_footbot10.py        # Quick run script for 10 footbots
│   ├── ray_footbot_aggregation.py       # RLlib PPO training for aggregation task
│   ├── ray_footbot_aggregation_result.py # Result visualization for aggregation training
│   └── tutorials/              # Tutorial scripts
│       ├── ray_pistonball.py           # PettingZoo Pistonball tutorial
│       └── ray_pistonball_result.py    # Pistonball result visualization
├── src/                        # Source code for the bridge
│   ├── plugin/                 # C++ ARGoS plugin source
│   │   ├── CMakeLists.txt
│   │   ├── common/
│   │   │   └── json.hpp        # nlohmann/json library for C++ JSON parsing
│   │   ├── controllers/
│   │   │   ├── CMakeLists.txt
│   │   │   ├── my_ipc_controller.cpp  # Per-robot controller (wheel & sensor logic)
│   │   │   └── my_ipc_controller.h
│   │   └── loop_functions/
│   │       ├── CMakeLists.txt
│   │       ├── zoo_loop_functions.cpp  # Central REP socket, batched observations
│   │       └── zoo_loop_functions.h
│   └── zoo/                    # Python package for the PettingZoo environment
│       ├── argos_env.py        # PettingZoo parallel env (batched REQ/REP client, compact schema support)
│       ├── zmq_client.py       # ZeroMQ client for connecting to ARGoS
│       ├── logging_utils.py    # Logging utilities
│       └── scenarios/          # Task-specific reward/metric callbacks
│           └── aggregation.py  # Aggregation scenario reward function
└── tests/                      # Tests for the Python components
    ├── conftest.py             # Pytest fixtures and configuration
    ├── test_env.py             # Environment integration tests
    ├── test_metrics_reward.py  # Reward function unit tests
    ├── test_logging.py         # Logging tests
    ├── test_parallel_api.py    # PettingZoo parallel API compliance tests
    ├── test_seed_layout.py     # Seed determinism tests
    ├── test_seed_positions_multi.py  # Multi-agent seed position tests
    ├── test_timeout_recovery.py      # Timeout and recovery tests
    ├── test_graceful_shutdown.py     # Graceful shutdown tests
    ├── test_legacy_removal.py        # Legacy code removal tests
    └── test_reward_variance.py       # Reward variance tests
```

## Developer Guide (FUP-13)

This section condenses the implementation details required to extend or debug the ARGoS ↔ Python bridge.

### 1. Discrete Action Mapping

The PettingZoo wrapper exposes a *uniform discrete* action space for every agent:

| Index | Logical Name | Wire Command (sent to C++) | Semantics |
|-------|--------------|----------------------------|-----------|
| 0 | `stop` | `stop` | Wheels halted |
| 1 | `forward` | `forward_speed` | Symmetric positive wheel velocity |
| 2 | `backward` | `backward_speed` | Symmetric negative wheel velocity |
| 3 | `turn_left` | `left_speed` | Differential turn (left on spot) |
| 4 | `turn_right` | `right_speed` | Differential turn (right on spot) |

Implementation reference: `ArgosEnv._action_index_to_name` and `_action_name_to_command` in `zoo/argos_env.py`. The environment accepts either the integer index or (for debugging) a string logical name / final wire command. Validation occurs in `_convert_action` (raises on out‑of‑range or unknown string).

Adding a new action only requires (a) appending its logical name to `_action_index_to_name`, (b) inserting a mapping entry to `_action_name_to_command`, and (c) teaching the C++ controller to interpret the new command string.

### 2. Timing & Step Synchronisation

Each `env.step(actions)` produces exactly *one* ARGoS tick (deterministic gating):

1. Python sends a batched `step` request containing the current tick's actions.
2. Loop functions apply the actions at the start of the *next* physics tick (`PreStep`).
3. The tick advances; controllers update sensors.
4. Observations are packaged (`PostStep`) and returned as one reply (Python derives rewards separately).
5. Python receives the reply and constructs per‑agent observation dictionaries.

This strict REQ/REP ordering (no pipelining) guarantees reproducible trajectories for identical seeds and action sequences (see FUP‑06 determinism goal). No internal buffering or multi‑tick batching is used.

### 3. Observation Schema

Wire schema (always `compact_v1`):

```jsonc
{
  "observations": {
    "schema": "compact_v1",
    "agents": ["robot_0", ...],
    "proximity": [[24 floats], ...],
    "position": [[x,y,z], ...]
  }
}
```

Python converts to per‑agent dicts with the active subset of features (currently only `proximity`). Length mismatches are auto padded/truncated with a single WARN (FUP‑03 resilience).

Extending with new sensors: append another parallel array (e.g. `light`, `imu`) and update the Python decoder. Only bump `schema` if a *breaking* semantic change occurs (renames, ordering changes, shape modifications). Non‑breaking additive fields leave the version unchanged.

### 4. Reward & Metrics (External Callback Ownership)

All MARL task logic (metrics, reward shaping, success detection) lives **outside** the core environment via a user‑supplied `reward_fn` callback. `ArgosEnv` itself is intentionally task‑agnostic and only:

1. Starts / restarts the simulator (seeded).
2. Translates actions ↔ wire commands.
3. Decodes compact batched observations into per‑agent dicts.
4. Provides a mutable per‑episode cache (`data['prev']`) to the callback.

The default behavior (no `reward_fn`) is a constant team reward of `0.0` with an empty metrics dict (`{"reward": 0.0}`).

Example (aggregation scenario) lives in `zoo/scenarios/aggregation.py`:
```
(team_reward, per_agent, metrics) = aggregation_reward(data)
```
Where `metrics` includes: `centroid`, `cohesion_mean`, `delta_cohesion`, `moved_mean`, `max_prox`, `success`, `reward`.

Callback data contract (passed each step):
```
{
  'step': int,
  'agents': List[str],
  'positions': np.ndarray|None (N,3),
  'proximities': Dict[agent, np.ndarray(24,)],
  'prev': dict  # mutable state cache persisted across steps in the episode
  'first_step': bool
}
```
Return contract:
```
(team_reward: float, per_agent: Optional[Dict[str,float]], metrics: Dict[str,Any])
```
If `per_agent` is `None`, the team reward is broadcast to all agents. Any exception inside the callback is caught; the environment logs a warning and substitutes `(0.0, None, {})` for that step (fail‑soft principle).

Design Rationale:
* Eliminates hidden scenario knobs from the core API (single extensibility mechanism).
* Hot‑swapping reward logic requires no recompilation or subclassing.
* Encourages pure, unit‑testable reward functions (see `tests/test_metrics_reward.py`).
* Prevents task leakage into C++ loop functions; the simulator remains reusable.

### 5. Seeding & Reproducibility

`env.reset(seed=s)` triggers regeneration of a *temporary seeded* `.argos` file: the `<experiment random_seed=...>` attribute is overwritten and the simulator subprocess is restarted (ARGoS only reads the seed at init). Providing the *same* seed consecutively avoids a restart but still reseeds the NumPy RNG used by policies/tests. See `_apply_seed_and_restart` for details.

Guidelines:
* Always call `reset(seed=...)` before collecting reference trajectories.
* Determinism assumes identical action sequences and absence of floating‑point nondeterminism across platforms (generally holds for single‑thread ARGoS).

### 6. Error Handling & Recovery

Failure modes and mitigations (FUP‑08, FUP‑12):

| Scenario | Detection | Mitigation |
|----------|-----------|------------|
| Lost / timed‑out reply | Poll timeout in `ZMQClient.send_command` | Socket recreation + `ping` handshake (`_recover`) |
| REQ/REP state desync (e.g., crash mid exchange) | Handshake failure | Raise, caller may re‑`reset()` or recreate env |
| Simulator crash | Subprocess return code != 0 | Reported on close; user should inspect ARGoS stderr prefix |
| Duplicate `close()` | `_closed` flag | Idempotent no‑op |
| Bad action index/string | Validation in `_convert_action` | Exception (fast fail) |

### 7. Scaling Model

Chosen approach: single REP socket (central batching). Benefits: constant descriptor count, reduced per‑agent handshake latency, and simpler recovery logic. Empirically validated up to 20 agents (benchmark numbers in README). Predicted practical ceiling dominated by JSON serialization O(N × feature_dim). Potential future paths:

* Binary framing (e.g. flatbuffers / Cap'n Proto) once proximity + future sensor arrays dominate payload size.
* Optional multi-socket sharding if per‑tick payload grows beyond ~100KB (not yet necessary).
* Incremental streaming (PUB/SUB side channel) for large continuous sensor feeds (e.g. cameras) while retaining REQ/REP for control gating.

### 8. Random Policy Example

Run a self‑contained random policy driver (no learning) for quick sanity checks:

```bash
PYTHONPATH=src python scripts/random_policy.py --argos experiments/footbot_10.argos --episodes 2 --steps 50 --seed 42
```

It will:
1. Create `ArgosEnv` (quiet by default).
2. Reset with the provided seed.
3. Sample discrete actions from each agent's `action_space` every step.
4. Accumulate per‑episode reward and print a concise summary.

See `scripts/random_policy.py` (added with FUP‑13) for extensible baseline usage.

### 9. Development Checklist (Extending the Env or Adding a Scenario)

1. Add new sensor in C++ (loop functions -> compact array field).
2. Extend decoder in `argos_env.py` (update observation space + extraction logic).
3. Write/extend a unit test validating shape & value ranges.
4. (Optional) Add new shaping term—implement in a new callback (do **not** modify C++ loop functions for reward logic).
5. Run `pytest -q` and the random policy script for smoke verification.

---

For deeper conceptual context see `concept.md`; for operational commands refer to `how-to-run.md`.

### 10. RL Compatibility Smoke Test (FUP-15)

To verify the bridge supports a basic learning signal without external RL frameworks, a minimal multi-agent stateless REINFORCE script (`scripts/rl_smoke.py`) is provided. It:

* Creates one softmax preference vector per agent (size = discrete action count).
* Samples actions each step; ignores observations (baseline functional check only).
* Collects full-episode discounted returns and applies a Monte Carlo policy gradient update with an exponential moving average baseline.
* Logs episode mean/total return and the mean probability of the `forward` action (index 1) which typically should rise over episodes if forward movement yields positive shaped reward.
* Optionally writes CSV metrics for quick plotting.

Example run:
```bash
PYTHONPATH=src python scripts/rl_smoke.py --argos experiments/footbot_10.argos \
  --episodes 20 --steps 50 --seed 123 --gamma 0.95 --lr 0.2 --csv rl_smoke.csv
```

Interpretation:
* Rising `mean_forward_prob` indicates the reward shaping supplies a differentiable learning signal.
* Stable or collapsing probabilities may signal reward saturation, excessive penalty weight, or lack of variance—tune Python shaping weights (`ArgosEnv` ctor params).
* Because observations are unused, this test isolates communication + reward plumbing correctness from representation learning concerns.

Extending the smoke test to observe-driven policies (future): replace stateless preferences with a linear layer over normalized proximity readings (concatenate across agents or per-agent independent policies) and include simple entropy regularization.

### Performance

Preliminary single-process benchmarks (MacBook Pro M1, experiment running on 20Hz):

```zsh
+--------+-------+---------+--------+--------+--------+------------+
| agents | steps | mean_ms | p95_ms | min_ms | max_ms | payload_kb |
+--------+-------+---------+--------+--------+--------+------------+
|      5 |   100 |   49.99 |  50.90 |  48.24 |  51.78 |       0.47 |
|     10 |   100 |   49.98 |  51.00 |  47.99 |  51.22 |       0.94 |
|     20 |   100 |   49.99 |  50.80 |  48.64 |  51.64 |       1.88 |
+--------+-------+---------+--------+--------+--------+------------+
```

- agents: Number of simulated robots (Foot-Bots) in the experiment.  
- steps: Number of measured simulation steps (excluding warmup).  
- mean_ms: Average duration of an `env.step()` call in milliseconds (ms) – corresponds to the mean simulation latency per tick.  
- p95_ms: 95th percentile of step latency (ms) – 95% of all steps are faster than this value (shows outliers).  
- min_ms: Shortest measured step latency (ms).  
- max_ms: Longest measured step latency (ms).  
- payload_kb: Average size of the transmitted sensor data per tick (in kilobytes, proximity arrays only, JSON-serialized).

---

## Integration Reference

This section provides the complete technical specification required to integrate the ARGoS-PettingZoo bridge into external systems.

### Dependencies

#### System Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | Tested on 3.11, 3.12, 3.13 |
| ARGoS3 | 3.0.0-beta59+ | `brew install argos3` on macOS |
| CMake | 3.15+ | For building C++ plugin |
| ZeroMQ | 4.3+ | C++ library: `brew install zeromq` |

#### Python Dependencies

```
pyzmq>=25.0.0      # ZeroMQ Python bindings
pettingzoo>=1.24.0 # Multi-agent environment API
gymnasium>=0.29.0  # Gymnasium spaces (Box, Discrete, Dict)
numpy>=1.24.0      # Array operations
psutil>=5.9.0      # Process management (optional, for tests)
pytest>=7.0.0      # Testing (dev only)
flake8>=6.0.0      # Linting (dev only)
```

#### C++ Dependencies

- **nlohmann/json**: Single-header JSON library (`src/plugin/common/json.hpp`)
- **cppzmq**: ZeroMQ C++ bindings (header-only, included with zeromq)

### Python API Reference

#### `ArgosEnv` Constructor

```python
from zoo.argos_env import ArgosEnv

env = ArgosEnv(
    argos_file: str,                    # Path to .argos configuration file (required)
    expected_num_agents: int | None = None,  # Validation: raise if agent count differs
    startup_delay: float = 3.0,         # Seconds to wait for simulator startup
    max_steps: int = 1000,              # Episode truncation limit
    client_timeout_ms: int = 5000,      # ZMQ request timeout before recovery
    log_level: str = "INFO",            # Python logger level: DEBUG|INFO|WARN|ERROR
    log_format: str = "text",           # Log format: "text" or "json"
    quiet: bool = False,                # If True, sets log_level to ERROR
    controller_log_level: str | None = None,  # Sets ARGOS_CONTROLLER_LOG_LEVEL env var
    loop_log_level: str | None = None,  # Sets ARGOS_LOOP_LOG_LEVEL env var
    reward_fn: Callable | None = None,  # Custom reward callback (see §4 Reward & Metrics)
    port: int | None = None,            # Explicit ZMQ port (default: auto-select)
    port_base: int = 5555,              # Base port for auto-selection fallback
    port_env_vars: tuple = ("ARGOS_ZMQ_PORT", "ZOO_ZMQ_PORT", "ZMQ_PORT"),
)
```

#### `reset()` Method

```python
def reset(
    self,
    seed: int | None = None,    # RNG seed; triggers simulator restart if changed
    options: dict | None = None # Optional: {"max_steps": int} to override episode length
) -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Returns:
        observations: {agent_id: {"proximity": ndarray(24,), "position": ndarray(3,)}, ...}
        infos: {agent_id: {"metrics": {"reward": 0.0}}, ...}
    """
```

#### `step()` Method

```python
def step(
    self,
    actions: dict[str, int | str]  # {agent_id: action_index_or_name, ...}
) -> tuple[
    dict[str, dict],    # observations
    dict[str, float],   # rewards
    dict[str, bool],    # terminations (always False; no terminal states)
    dict[str, bool],    # truncations (True when timestep >= max_steps)
    dict[str, dict],    # infos with metrics
]:
```

#### `close()` Method

```python
def close(self) -> None:
    """Gracefully terminate simulator subprocess and release resources.
    Idempotent: safe to call multiple times.
    """
```

#### Helper Methods

```python
def observation_space(self, agent: str) -> gymnasium.spaces.Dict
def action_space(self, agent: str) -> gymnasium.spaces.Discrete
def get_last_positions(self) -> list[list[float]] | None  # Raw positions from last reply
def validate_observation_spaces(self) -> bool  # Runtime shape validation
```

### Gymnasium Spaces

#### Observation Space

```python
gymnasium.spaces.Dict({
    "position": gymnasium.spaces.Box(
        low=-np.inf,
        high=np.inf,
        shape=(3,),
        dtype=np.float32
    ),
    "proximity": gymnasium.spaces.Box(
        low=0.0,
        high=1.0,
        shape=(24,),
        dtype=np.float32
    )
})
```

- **position**: Robot's 3D coordinates `[x, y, z]` in arena frame (meters)
- **proximity**: 24 infrared proximity sensor readings, normalized to `[0, 1]` where:
  - `0.0` = no obstacle detected
  - `1.0` = obstacle at minimum range
  - Sensors arranged radially around the robot body at 15° intervals

#### Action Space

```python
gymnasium.spaces.Discrete(5)
```

| Index | Name | Wire Command | Behavior |
|-------|------|--------------|----------|
| 0 | `stop` | `stop` | Halt both wheels |
| 1 | `forward` | `forward_speed` | Both wheels forward (10 cm/s default) |
| 2 | `backward` | `backward_speed` | Both wheels backward |
| 3 | `turn_left` | `left_speed` | Differential turn left (on-spot rotation) |
| 4 | `turn_right` | `right_speed` | Differential turn right |

### Wire Protocol Specification

All communication uses JSON over ZeroMQ REQ/REP sockets on TCP.

#### Request Format (Python → C++)

```json
{
  "command": "<command_name>",
  "payload": { ... }
}
```

#### Commands

**`ping`** - Connection health check / handshake
```json
// Request
{"command": "ping", "payload": {"t": 0}}

// Response
{"observations": {"schema": "compact_v1", "agents": [...], "proximity": [...], "position": [...]}}
```

**`reset`** - Reset simulation to initial state
```json
// Request
{"command": "reset", "payload": {}}

// Response
{"observations": {"schema": "compact_v1", "agents": ["robot_0", ...], "proximity": [[...], ...], "position": [[x,y,z], ...]}}
```

**`step`** - Execute one simulation tick with given actions
```json
// Request
{
  "command": "step",
  "payload": {
    "actions": {
      "robot_0": "forward_speed",
      "robot_1": "left_speed",
      "robot_2": "stop"
    }
  }
}

// Response
{
  "observations": {
    "schema": "compact_v1",
    "agents": ["robot_0", "robot_1", "robot_2"],
    "proximity": [
      [0.0, 0.0, 0.1, ..., 0.0],  // 24 floats per agent
      [0.0, 0.2, 0.0, ..., 0.0],
      [0.0, 0.0, 0.0, ..., 0.3]
    ],
    "position": [
      [1.2, 0.5, 0.0],  // [x, y, z] per agent
      [-0.3, 1.1, 0.0],
      [0.0, 0.0, 0.0]
    ]
  }
}
```

**`close`** - Signal shutdown (no response expected)
```json
{"command": "close", "payload": {}}
```

**`set_loop_log_level:<LEVEL>`** - Dynamically change C++ log verbosity
```json
{"command": "set_loop_log_level:DEBUG", "payload": {}}
```

### ARGoS Configuration Guide

The `.argos` XML configuration must include specific elements for the bridge to function.

#### Minimal Configuration Template

```xml
<?xml version="1.0" ?>
<argos-configuration>
  <framework>
    <system threads="0" />
    <experiment length="0" ticks_per_second="50" random_seed="123" />
  </framework>

  <!-- Controller plugin registration -->
  <controllers>
    <my_ipc_controller id="ipc" library="build/src/plugin/controllers/libmy_ipc_controller.dylib">
      <actuators>
        <differential_steering implementation="default" />
      </actuators>
      <sensors>
        <footbot_proximity implementation="default" show_rays="false" />
      </sensors>
      <params />
    </my_ipc_controller>
  </controllers>

  <!-- Loop functions with ZMQ server -->
  <loop_functions
    library="build/src/plugin/loop_functions/libzoo_loop_functions.dylib"
    label="zoo_loop_functions">
    <params zmq_port="5555" />
  </loop_functions>

  <!-- Arena with robots -->
  <arena size="6,6,1" center="0,0,0.5">
    <foot-bot id="fb_0">
      <body position="0,0,0" orientation="0,0,0" />
      <controller config="ipc" />
    </foot-bot>
    <!-- Add more foot-bot elements as needed -->
  </arena>

  <physics_engines>
    <dynamics2d id="dyn2d" />
  </physics_engines>

  <media />
</argos-configuration>
```

#### Key Configuration Elements

| Element | Attribute | Description |
|---------|-----------|-------------|
| `<experiment>` | `random_seed` | RNG seed (overwritten by `env.reset(seed=...)`) |
| `<experiment>` | `ticks_per_second` | Simulation frequency (50 = 20ms per tick) |
| `<experiment>` | `length` | Set to `0` for infinite (Python controls termination) |
| `<my_ipc_controller>` | `library` | Path to compiled controller `.dylib`/`.so` |
| `<loop_functions>` | `library` | Path to compiled loop functions `.dylib`/`.so` |
| `<loop_functions>/<params>` | `zmq_port` | ZMQ server port (can also use env var) |
| `<foot-bot>` | `id` | Robot identifier (mapped to `robot_N` internally) |

#### Visual vs Headless Configurations

- **Headless** (training): Omit `<visualization>` section entirely
- **Visual** (debugging): Add ARGoS Qt-OpenGL visualization:

```xml
<visualization>
  <qt-opengl>
    <camera>
      <placements>
        <placement index="0" position="0,0,8" look_at="0,0,0" up="0,1,0" />
      </placements>
    </camera>
  </qt-opengl>
</visualization>
```

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ARGOS_ZMQ_PORT` | `5555` | ZMQ port for Python↔C++ communication |
| `ZOO_ZMQ_PORT` | - | Alternative port variable (fallback) |
| `ZMQ_PORT` | - | Alternative port variable (fallback) |
| `ARGOS_ZMQ_PORT_BASE` | `5555` | Base port for auto-selection when not specified |
| `ARGOS_LOOP_LOG_LEVEL` | `INFO` | C++ loop functions log level: DEBUG\|INFO\|WARN\|ERROR |
| `ARGOS_CONTROLLER_LOG_LEVEL` | `INFO` | C++ controller log level: DEBUG\|INFO\|WARN\|ERROR |

Port resolution priority:
1. Explicit `port=` constructor argument
2. `ARGOS_ZMQ_PORT` environment variable
3. `ZOO_ZMQ_PORT` environment variable
4. `ZMQ_PORT` environment variable
5. Auto-select free port (OS ephemeral or probe from `port_base`)

### PettingZoo API Compliance

`ArgosEnv` implements the **PettingZoo Parallel API**:

```python
from pettingzoo import ParallelEnv

class ArgosEnv(ParallelEnv):
    metadata = {"render_modes": ["human"], "name": "argos_v0"}

    # Required attributes
    possible_agents: list[str]      # All agent IDs (set after first reset)
    agents: list[str]               # Currently active agents
    agent_name_mapping: dict        # {agent_id: index}

    # Required methods
    def reset(seed, options) -> (observations, infos)
    def step(actions) -> (observations, rewards, terminations, truncations, infos)
    def observation_space(agent) -> Space
    def action_space(agent) -> Space
    def close() -> None
```

**Compatibility notes:**
- All agents share identical observation and action spaces
- No agent termination during episode (only truncation at `max_steps`)
- Rewards computed externally via `reward_fn` callback
- Supports `env.unwrapped` access pattern

### Build Instructions

#### macOS (Apple Silicon / Intel)

```bash
# 1. Install system dependencies
brew install argos3 zeromq cmake

# 2. Clone and enter repository
git clone <repository_url>
cd ArgosToZoo

# 3. Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install numpy gymnasium  # If not in requirements.txt

# 4. Build C++ plugins
rm -rf build && mkdir build && cd build
cmake ..
make
cd ..

# 5. Verify installation
PYTHONPATH=src python -c "from zoo.argos_env import ArgosEnv; print('OK')"
```

#### Linux (Ubuntu/Debian)

```bash
# Install ARGoS from source or PPA (see argos3 documentation)
# Install ZeroMQ: apt install libzmq3-dev
# Follow same build steps as macOS
```

### Quick Start Example

```python
import numpy as np
from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward

# Create environment with aggregation reward
env = ArgosEnv(
    argos_file="experiments/footbot_10.argos",
    max_steps=500,
    reward_fn=aggregation_reward,
    quiet=True,
)

# Run one episode
obs, infos = env.reset(seed=42)
total_reward = 0.0

for step in range(500):
    # Random policy
    actions = {agent: env.action_space(agent).sample() for agent in env.agents}
    obs, rewards, terms, truncs, infos = env.step(actions)
    total_reward += sum(rewards.values())

    if all(truncs.values()):
        break

print(f"Episode reward: {total_reward:.2f}")
env.close()
```

### Integration with RLlib

```python
from ray.rllib.env import PettingZooEnv
from ray.rllib.algorithms.ppo import PPOConfig
from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward

def env_creator(config):
    return ArgosEnv(
        argos_file=config.get("argos_file", "experiments/footbot_10.argos"),
        max_steps=config.get("max_steps", 500),
        reward_fn=aggregation_reward,
        quiet=True,
    )

# Register and train
from ray.tune.registry import register_env
register_env("argos_aggregation", lambda cfg: PettingZooEnv(env_creator(cfg)))

config = (
    PPOConfig()
    .environment("argos_aggregation", env_config={"max_steps": 500})
    .framework("torch")
)
algo = config.build()
```
