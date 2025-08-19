[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md)

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

1. **Central REP Socket:** Implemented in `zoo_loop_functions.cpp`; all agent actions are applied in `PreStep()`, and a single response with all observations + rewards is sent in `PostStep()`.
2. **Agent Indexing:** Agents are deterministically named `robot_0..robot_{N-1}` in discovery order. Python infers the set after the first reset.
3. **Batch Payloads:** Request JSON: `{ "command": "step", "payload": { "actions": { "robot_0": "forward_speed", ... }}}`. Response JSON contains an `observations` object.
4. **Unified Observation Schema:** The environment always emits the compact batched envelope:
   ```json
   {
     "observations": {
       "schema": "compact_v1",
       "agents": ["robot_0", "robot_1"],
       "proximity": [[...24 floats...], [...]],
       "position": [[x,y,z], [...]],
       "rewards": {"robot_0": 0.0, "robot_1": 0.01}
     }
   }
   ```
   This minimizes repeated keys and lowers serialization overhead. A developer utility (future work) can pretty‑print this into per‑agent dictionaries for manual debugging without changing the wire protocol.
5. **Extensibility:** Additional sensors append new parallel arrays (e.g., `light`, `battery`) and increment the schema version only if breaking changes are introduced.

## Control Flow

The typical control flow for a simulation step is as follows:

1. The ARGoS simulator runs and calls the loop functions `PreStep()` and `PostStep()` each tick.
2. `PostStep()` collects observations (and computes rewards) and blocks waiting for the next batched request from Python (REQ/REP ensures sync).
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
│   └── footbot_5.argos     # Scenario with five robots
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
