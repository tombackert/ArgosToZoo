# ArgosToZoo

[**Concept**](#concept) | [**How to Run**](#how-to-run) | [**Milestones**](#project-management) | [**Resources**](#resources)

**ArgosToZoo** bridges the high-performance ARGoS simulator with popular Multi-Agent Reinforcement Learning (MARL) libraries. It enables the seamless integration of complex swarm robotics experiments into modern Python-based RL workflows.

## Overview

- 🚀 **Project Goal:** To create a robust bridge for controlling ARGoS agents using an external Python policy, with the ultimate aim of simulating collective behaviors (e.g., collective transport) trained with MARL.
- 🏎️ **Architecture:** The system is built on a decoupled client–server architecture. Each robot in ARGoS runs a C++ controller that acts as a ZeroMQ server (REP). An external Python script acts as the client (REQ), sending commands and receiving state information. This ensures the high-performance simulation is handled by C++, while flexible decision-making resides in Python.

## Tech Stack

- 🤖 **ARGoS (C++):** Simulates the environment and the physics of the agents.
- 🛜 **ZeroMQ (C++ & Python):** Handles high-performance, low-latency message passing between the C++ simulator and the Python controller via the REQ/REP pattern.
- 📄 **nlohmann/json (C++):** A lightweight, header-only library for serializing and deserializing data sent over the ZeroMQ bridge.
- 🧠 **PettingZoo (Python):** The target framework for wrapping the simulation environment to make it compatible with standard MARL algorithms.

## Concept

Data in ArgosToZoo flows as follows:

1. **ARGoS (Server):** The C++ controller for each agent starts a ZeroMQ REP server on a unique port and waits for commands. To prevent simulation freezing, it checks for messages non-blockingly.
2. **Python (Client):** The Python script starts ZeroMQ REQ clients, connecting to each agent's port.
3. **Action Selection:** The Python script (initially manual input, later a MARL policy) decides on an action for each agent.
4. **Serialization (Python → C++):** Actions (e.g., wheel speeds) are formatted into a JSON string and sent as a request to the corresponding ARGoS agent.
5. **Execution:** The C++ controller receives the JSON request, parses it, and applies actions to the robot’s actuators.
6. **Serialization (C++ → Python):** The controller sends a JSON confirmation reply (e.g., `{"status": "ok"}`), which can be extended to include sensor data/observations.
7. **Loop:** The cycle continues.

![ARGoS-Python Communication Architecture](docs/argos-python-flowchart.png)

## How to Run

These instructions are for macOS (Apple Silicon/ARM64).

### 1. Install Dependencies

**Core Dependencies (via Homebrew):**
```bash
brew install pkg-config cmake libpng freeimage qt freeglut lua docbook asciidoc graphviz doxygen zeromq cppzmq clang-format
```

**Python Packages:**
```bash
pip install -r requirements.txt
```

**C++ JSON Library:**
1. Download `json.hpp` from the [nlohmann/json releases](https://github.com/nlohmann/json/releases).
2. Create directory `plugin/common/`.
3. Place `json.hpp` in `plugin/common/`.

### 2. Compile the Plugin

Run all commands from the project root (`ArgosToZoo/`):
```bash
rm -rf build              # (Optional) Clean previous builds
mkdir build && cd build   # Create and enter build directory
cmake ..                  # Configure project
make                      # Compile the C++ controller plugin
```
The compiled library `libmy_ipc_controller.dylib` will be in `build/controllers/`.

### 3. Run the Experiment

Open two terminals in the project root:

**Terminal 1: ARGoS Simulator (C++ Server)**
```bash
argos3 -c experiments/test.argos
```

**Terminal 2: Python Client**
```bash
python manual_control.py
```

Control the robots by typing `w`, `a`, `s`, `d`, or `stop` in the Python terminal.

## Testing

The automated test suite (FUP-11) validates:

| Area | Purpose |
|------|---------|
| API compliance | PettingZoo parallel API structure & lifecycle |
| Reward variance | Ensures non-constant shaping signal |
| Seeding | Deterministic restart & simulator re-seed logic |
| Timeout recovery | Socket resilience (ZeroMQ reconnection) |
| Graceful shutdown | Idempotent `close()` & process cleanup |

Full local run (all available tests):
```bash
pytest -q
```

Fast logic-only selection (skips named integration-style tests):
```bash
pytest -k "not timeout and not graceful" -q
```

PettingZoo API smoke check (manual):
```bash
python -m pettingzoo.test.parallel_api_test zoo.argos_env:ArgosEnv
```

Style-only lint:
```bash
flake8 src/zoo
```

CI mapping (`.github/workflows/ci.yml`):
- Feature branch push → fast Python job (ARGoS-dependent tests auto-skip if binary missing).
- PR to main / push on main → full integration job builds ARGoS & runs entire suite.

## CI & Development Workflow

The CI (see `.github/workflows/ci.yml`) is optimized for quick Python feedback on feature branches and full integration guarantees on PRs/main:

| Scenario | Job | What runs | ARGoS Build | Approx Time |
|----------|-----|-----------|-------------|-------------|
| Push to feature branch | `fast-python` | flake8 (Python), pytest (all tests; ARGoS tests auto-skip if no binary) | No | ~1–2 min |
| Pull Request → `main` | `full-integration` | Brew deps, ARGoS clone + cached incremental build, C++ lint, plugin build, full pytest | Yes | ~5–7 min first run; faster with cache |
| Push to `main` | `full-integration` | Same as PR | Yes | ~5–7 min |

Caching: The ARGoS build directory (`argos3/build`) is cached. Subsequent PR runs reuse object files, cutting incremental build time. The install step always runs to ensure the `argos3` binary is on PATH.

Manual local full integration test (mirrors CI):
```bash
brew install pkg-config cmake libpng freeimage qt freeglut lua docbook asciidoc graphviz doxygen zeromq cppzmq clang-format
git clone https://github.com/ilpincy/argos3.git
cd argos3 && mkdir build && cd build
cmake -DCMAKE_CXX_STANDARD=17 ../src && make -j$(sysctl -n hw.ncpu) && make doc && sudo make install
cd ../../
pip install -r requirements.txt
pytest -q
```

Troubleshooting CI:
- ARGoS not found: Check the log section "Build & Install ARGoS" and confirm `argos3 -q version` output.
- Cache not used: Ensure cache key hasn't changed (CMakeLists modifications re-trigger full compile).
- Failing C++ lint: Run `clang-format -i` locally on `src/plugin/**/*.cpp` & `*.h`.
- Skipped integration tests in `fast-python`: This is expected; they re-run fully in the PR job.

Contribution Guidelines (short):
1. Create feature branch: `git checkout -b feature/<short-name>`.
2. Write/adjust tests first (reward, seeding, recovery, shutdown).
3. Run local lint & tests: `flake8 src/zoo && pytest -q`.
4. Push (fast CI). Open PR to trigger full integration.
5. Merge only when full integration green.






## Project Management

<details>
<summary>🏁 Milestones</summary>

**M1 – Infrastructure & Prototype (≈30 h)**
- Set up ARGoS dev environment (build, plugins, scenarios)
- Implement C++ ZeroMQ skeleton (REQ/REP)
- First end-to-end message: observation → Python → acknowledgment

**M2 – Python Wrapper & PettingZoo (≈40 h)**
- Develop `ArgosEnv` according to PettingZoo Parallel API
- Map JSON to obs/reward/done dictionaries
- Unit tests for wrapper & handshake

**M3 – Benchmark Scenario & MARL (≈50 h)**
- Define collective transport task with 5 agents
- Integrate MARL algorithm (e.g., PPO via RLlib/TorchRL)
- Initial training: hyperparameters, logging, TensorBoard

**M4 – Evaluation & Documentation (≈30 h)**
- Analyze training progress & stability
- Optimize communication pipeline
- Final documentation (diagrams, protocol specs)

</details>

<details>
<summary>🌀 Agile Approach</summary>

- **Product Backlog & Stories:** Kanban board (GitHub Issues)
- **Two-Week Sprints (~25 h):** Plan, review, retrospectives
- **Definition of Done:** Code compiles, docs updated, example works, issue closed
- **Meeting Structure:** Bi-weekly reviews & weekly check-ins

</details>

## Resources

- **ARGoS:** [Modular, parallel, multi-engine simulator](https://doi.org/10.1007/s11721-012-0072-5)
- **PettingZoo Parallel API:** [Documentation](https://pettingzoo.farama.org/api/parallel/) | [Paper](https://arxiv.org/pdf/2009.14471)
- **Ray RLlib:** [RLlib Docs](https://docs.ray.io/en/latest/rllib/index.html) | [Multi-Agent](https://docs.ray.io/en/latest/rllib/multi-agent-envs.html) | [External Env](https://docs.ray.io/en/latest/rllib/external-envs.html)
- **ZeroMQ:** [Official Site](https://zeromq.org/)
- **Research:** [Swarm robotics RL overview](https://doi.org/10.1016/j.cogr.2023.07.004)
