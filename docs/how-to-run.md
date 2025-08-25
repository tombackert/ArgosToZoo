[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md)

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
# Python bindings for ZeroMQ
pip install pyzmq

# MARL framework (for future integration)
pip install pettingzoo
```

### Manual Dependencies

1. Download the single-header file `json.hpp` from [nlohmann/json releases](https://github.com/nlohmann/json/releases) or `brew install nlohmann/json`.
2. Create a directory `plugin/common/` in the project root.
3. Place the `json.hpp` file in this directory.

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

After successful compilation, you should find `libmy_ipc_controller.dylib` in the `build/controllers/` directory.

## 3. Run the Experiment

The system requires two separate terminal sessions running concurrently. Both terminals must be in the project root (`ArgosToZoo/`).

### Terminal 1: Start ARGoS Simulator

In this terminal, start the ARGoS simulation. The simulation will load, and the C++ controllers will wait for commands from Python.

```bash
argos3 -c experiments/test.argos
```

Robots in the GUI will remain idle until the Python script starts.

### Terminal 2: Start Python Control Script

In this terminal, start the Python client that sends control commands.

```bash
python manual_control.py
```

After startup, you will be prompted to enter commands. Type `w`, `a`, `s`, `d`, or `stop` and press Enter to control the robots in the ARGoS GUI.
