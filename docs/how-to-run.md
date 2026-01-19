[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md) | [Results](results.md) | [Backlog](backlog.md)

# How to Run: ARGoS-PettingZoo Bridge

This document describes the steps to run the project that connects the ARGoS simulator with an external Python control script.

## 1. Install Dependencies

Ensure all required dependencies are installed on macOS (ARM64/Apple Silicon).

### C++ / ARGoS Environment

Use Homebrew to install:

```bash
# ARGoS Simulator and its dependencies
brew install argos3

# ZeroMQ messaging library
brew install zeromq

# CMake build system
brew install cmake
```

### Python Environment

Use `pip` inside a virtual environment of your choice:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Additional dependencies (if not in requirements.txt)
pip install numpy gymnasium
```

### Manual Dependencies

1. Download the single-header file `json.hpp` from [nlohmann/json releases](https://github.com/nlohmann/json/releases) or `brew install nlohmann/json`.
2. The file should be placed at `src/plugin/common/json.hpp` (already included in repository).

## 2. Build the Project

The C++ controller must be built before running. Execute the following commands from the project root (`ArgosToZoo/`):

```bash
# 1. (Optional but recommended) Clean build by removing the old build directory
rm -rf build

# 2. Create a new build directory and enter it
mkdir build && cd build

# 3. Run CMake to configure the build system
cmake ..

# 4. Compile the controller plugin
make
```

After successful compilation, you should find:
- `build/src/plugin/controllers/libmy_ipc_controller.dylib`
- `build/src/plugin/loop_functions/libzoo_loop_functions.dylib`

## 3. Run the Experiment

There are two ways to run experiments: **Manual Mode** (two terminals) or **Programmatic Mode** (recommended).

### Option A: Programmatic Mode (Recommended)

Use the Python environment wrapper which handles simulator lifecycle automatically:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run random policy test
PYTHONPATH=src python scripts/random_policy.py \
    --argos experiments/footbot_10.argos \
    --episodes 2 --steps 50 --seed 42

# Run with visual feedback (requires Qt-OpenGL ARGoS build)
PYTHONPATH=src python scripts/random_policy.py \
    --argos experiments/visual/footbot_10_vis.argos \
    --episodes 1 --steps 100
```

### Option B: Manual Mode (Two Terminals)

For debugging or manual control, run ARGoS and Python separately.

**Terminal 1: Start ARGoS Simulator**

```bash
# Headless mode (training)
argos3 -c experiments/footbot_10.argos

# Or with visualization (debugging)
argos3 -c experiments/visual/footbot_10_vis.argos
```

The simulation will load and wait for commands from Python.

**Terminal 2: Start Python Control Script**

```bash
source .venv/bin/activate
PYTHONPATH=src python scripts/manual_control.py
```

After startup, you will be prompted to enter commands. Type `w`, `a`, `s`, `d`, or `stop` and press Enter to control the robots.

## 4. Available Experiment Configurations

| File | Agents | Mode | Description |
|------|--------|------|-------------|
| `experiments/footbot_1.argos` | 1 | Headless | Single robot testing |
| `experiments/footbot_5.argos` | 5 | Headless | Small swarm |
| `experiments/footbot_10.argos` | 10 | Headless | Default training scenario |
| `experiments/footbot_20.argos` | 20 | Headless | Larger swarm |
| `experiments/visual/footbot_*_vis.argos` | Various | Visual | Qt-OpenGL visualization |

## 5. Quick Verification

Run the test suite to verify everything is working:

```bash
source .venv/bin/activate
PYTHONPATH=src pytest tests/ -v
```

## 6. Troubleshooting

| Issue | Solution |
|-------|----------|
| `Library not found: libmy_ipc_controller.dylib` | Rebuild: `cd build && make` |
| `Connection refused` on ZMQ | Ensure ARGoS is running first (manual mode) |
| `ModuleNotFoundError: zoo` | Set `PYTHONPATH=src` before running Python |
| Port already in use | Set `ARGOS_ZMQ_PORT=5556` or use `port=` parameter |
