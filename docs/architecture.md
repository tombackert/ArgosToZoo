[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md)

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
├── CMakeLists.txt          # Main CMake configuration for the C++ plugin
├── README.md               # Project overview, setup, and usage instructions
├── build/                  # Compiled C++ binaries and build artifacts (auto-generated)
├── docs/                   # Documentation, diagrams, and architectural notes
│   ├── architecture.md     # This file
│   ├── concept.md          # High-level project concept
│   └── how-to-run.md       # Detailed setup and execution guide
├── experiments/            # ARGoS configuration files (.argos) for different scenarios
│   ├── footbot_1.argos     # Scenario with one robot
│   └── footbot_10.argos    # Headless aggregation scenario with ten robots
├── requirements.txt        # Python dependencies
├── scripts/                # Standalone Python scripts for control and interaction
│   └── manual_control.py   # Script for manually controlling robots via the terminal
├── src/                    # Source code for the bridge
│   ├── plugin/             # C++ ARGoS plugin source
│   │   ├── CMakeLists.txt
│   │   ├── common/
│   │   │   └── json.hpp    # nlohmann/json library for C++ JSON parsing
│   │   ├── controllers/
│   │   │   ├── my_ipc_controller.cpp # Per-robot controller (wheel & sensor logic)
│   │   │   └── my_ipc_controller.h
│   │   └── loop_functions/ # 
│   └── zoo/                # Python package for the PettingZoo environment
│       ├── argos_env.py    # PettingZoo parallel env (batched REQ/REP client, compact schema support)
│       ├── test_env.py     # Script to test the environment
│       └── zmq_client.py   # ZeroMQ client for connecting to ARGoS
└── tests/                  # Tests for the Python components
    └── test_example.py
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
