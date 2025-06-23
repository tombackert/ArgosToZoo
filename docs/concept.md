[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md)

# Project Concept: A Bridge between ARGoS and PettingZoo

This document describes the overarching goal and the conceptual foundations of the project.

## Vision

The goal of this project is to create a robust and high-performance bridge between the highly realistic multi-robot simulator **ARGoS** and the **PettingZoo** framework, the de facto standard for multi-agent reinforcement learning (MARL) in Python.

The final product should enable researchers and developers to develop complex, machine-learning-based swarm intelligence algorithms with modern Python libraries (such as PyTorch or TensorFlow) and train and validate them seamlessly in a physically accurate 3D environment without dealing with the details of the C++ simulation layer.

## Core Components and Their Roles

### 1. ARGoS: The Simulation Environment

- **Role:** ARGoS provides the "physics" and the "world" for the robots. It handles realistic simulation of movement, collision, and sensing.
- **Why ARGoS?** It is specifically designed for simulating large, heterogeneous robot swarms and offers high performance through its modular C++ architecture.
- **Implementation:** The connection to ARGoS is made via a custom **controller plugin**. This C++ plugin is the only component that interacts directly with the simulator and contains the server logic for the communication bridge.

### 2. Python/PettingZoo: The Intelligence of the Agents

- **Role:** The Python side implements the agents' decision-making logic, processing observations and generating actions.
- **Why PettingZoo?** PettingZoo provides a standardized API for MARL environments, similar to Gymnasium for single-agent RL. This enables algorithm reuse and easy integration with established RL libraries.
- **Implementation:** The goal is to create a custom `pettingzoo.ParallelEnv` class that encapsulates the communication logic and presents the ARGoS simulator as a standard PettingZoo environment.
  - The environment's `step(actions)` method will send the RL agents' actions over the IPC bridge to the C++ controllers.
  - Sensor data returned by the controllers will be delivered as observations, rewards, etc., to the RL algorithms.

### 3. The IPC Bridge: Connecting C++ and Python

- **Role:** The bridge decouples the simulation environment from the agent logic—a crucial design principle that enables flexibility and modularity.
- **Technology:** The bridge is based on **ZeroMQ** and **JSON**. ZeroMQ provides fast and reliable message delivery, while JSON ensures language-agnostic and human-readable data exchange.
- **Operation:** Each robot in the ARGoS simulator acts as a **REP server** waiting for commands. The PettingZoo environment in Python acts as a **REQ client** that sends commands and awaits responses (the next observation).

## Summary Diagram of the Concept

```text
+-------------------------------+                          +-------------------------------------+
|         Python Process        |                          |         ARGoS Process (C++)         |
|-------------------------------|                          |-------------------------------------|
| +--------------------------+  |                          | +--------------------------------+  |
| | MARL Algorithm (e.g.,    |  |                          | | Simulation Engine              |  |
| | PPO, DQN)                |  |                          | | (Physics, Sensing, Actuation)  |  |
| +--------------------------+  |                          | +--------------------------------+  |
|             ^                 |                          |                ^                    |
|     Actions/Obs.              |                          |      Commands/Sensor Data           |
|             v                 |                          |                v                    |
| +--------------------------+  | <-- IPC Communication--> | +--------------------------------+  |
| | PettingZoo Env Wrapper   |  |  (ZeroMQ: REQ Sockets)   | | Custom Controller Plugin       |  |
| | (Python Client)          |  |                          | | (C++ Server, REP Sockets)      |  |
| +--------------------------+  |                          | +--------------------------------+  |
+-------------------------------+                          +-------------------------------------+
```
