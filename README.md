# ArgosRLink

What? ArgosRLink provides an interface between the ARGoS robot simulator and popular Multi-Agent Reinforcement Learning (MARL) libraries. It enables realistic swarm robotics experiments to be integrated into modern reinforcement learning workflows.

Goal? Proof of Concept. Successfully simulate a collective transportation behavior with 5 agents in ARGoS using MARL via an external Python policy.

## Concept

The architecture is based on asynchronous communication between the C++-based ARGoS simulator and a Python MARL environment using ZeroMQ as the communication bridge.

Architecture Overview

+ ARGoS (C++): Simulates the environment and physical agents.
+ ZeroMQ (IPC): Handles message passing between C++ and Python.
+ PettingZoo (Python): Wraps the environment to interface with MARL libraries.

Data Flow

1. ARGoS simulates the environment and computes observations, rewards, and done flags.
2. Serialization (C++ → Python): Data is serialized (e.g., JSON) and sent via ZeroMQ.
3. PettingZoo wrapper receives the data and formats it into standard MARL-compatible dictionaries.
4. MARL algorithm (e.g., via RLlib or TorchRL) selects actions for each agent.
5. Serialization (Python → C++): Actions are sent back over ZeroMQ.
6. ARGoS applies the actions and advances the simulation.
7. The loop continues…

Visual

*implement diagram here*


Planned Implementation

+ Build a C++ ARGoS module that communicates over ZeroMQ.
+ Develop a Python wrapper conforming to the PettingZoo Parallel API.
+ Define a minimal Collective Transport Task as a benchmark scenario.
+ Integrate with a MARL library (e.g., RLlib or TorchRL).
+ Train and validate the policy to solve the task successfully.

## Project Milestones

*tba*

## Resources

+ Technical References
    + PettingZoo Parallel API
        + https://pettingzoo.farama.org/api/parallel/
        + https://arxiv.org/pdf/2009.14471
    + Ray RLlib
        + https://docs.ray.io/en/latest/rllib/index.html
        + https://docs.ray.io/en/latest/rllib/multi-agent-envs.html
        + https://docs.ray.io/en/latest/rllib/external-envs.html
    + ZeroMQ
        + https://zeromq.org/