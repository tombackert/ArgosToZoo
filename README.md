# ArgosRLink

[**Concept**](#concept) | [**Milestones**](#project-milestones) | [**Resources**](#resources)

**ArgosRLink** bridges the ARGoS sim & popular MARL libraries, enabling seamless integration of swarm robotics experiments into modern Reinforcement Learning (RL) workflows.

## Overview

- 🚀 Project Goal: Successfully simulate a collective transportation behavior with 5 agents in ARGoS using MARL via an external Python policy

- 🏎️ The architecture is based on asynchronous communication between the C++-based ARGoS simulator and a Python MARL environment using ZeroMQ as the communication bridge.

## Tech Stack

+ 🤖 ARGoS (C++): Simulates the environment and physical agents.
+ 🛜 ZeroMQ (IPC): Handles message passing between C++ and Python.
+ 🧠 PettingZoo (Python): Wraps the environment to interface with MARL libraries.

## Concept

Data in ArgosRLink flows as follows:

1. ARGoS simulates the environment and computes observations, rewards, and done flags.
2. Serialization (C++ → Python): Data is serialized (e.g., JSON) and sent via ZeroMQ.
3. PettingZoo wrapper receives the data and formats it into standard MARL-compatible dictionaries.
4. MARL algorithm (e.g., via RLlib or TorchRL) selects actions for each agent.
5. Serialization (Python → C++): Actions are sent back over ZeroMQ.
6. ARGoS applies the actions and advances the simulation.
7. The loop continues…

![ARGoS-Python Communication Architecture](docs/argos-python-flowchart.png)


## Planned Implementation

+ Build a C++ ARGoS module that communicates over ZeroMQ.
+ Develop a Python wrapper conforming to the PettingZoo Parallel API.
+ Define a minimal Collective Transport Task as a benchmark scenario.
+ Integrate with a MARL library (e.g., RLlib or TorchRL).
+ Train and validate the policy to solve the task successfully.


## Project Milestones

- **M1 – Infrastructure & Prototype (approx. 30 h)**
    - Set up ARGoS development environment (build, plugins, example scenarios)
    - Implement C++ skeleton for ZeroMQ communication (sender/receiver)
    - First end-to-end message: Observation → Python → Acknowledgement back

- **M2 – Python Wrapper & PettingZoo Environment (approx. 40 h)**
    - Develop an `ArgosEnv` class according to the PettingZoo Parallel API
    - Map JSON messages to observation/reward/done dictionaries
    - Unit tests for wrapper functions and ZeroMQ handshake (→ Communication channel needs to work)

- **M3 – Benchmark Scenario & MARL Integration (approx. 50 h)**
    - Define and configure the collective transport task with 5 agents in ARGoS
    - Integrate a MARL algorithm (e.g., PPO via RLlib or TorchRL)
    - Initial training runs: base hyperparameters, logging, TensorBoard setup

- **M4 – Evaluation, Optimization & Documentation (approx. 30 h)**
    - Analyze training progress (success criteria, stability)
    - Optimize communication pipeline (buffering, latency) and parameter tuning
    - Create final documentation (architecture diagrams, protocol specification)

## Agile Approach

- **Product Backlog & User Stories**
    - Create a Kanban board (GitHub Issues) with stories
    - Ongoing prioritization and maintenance of the backlog
- **Two-Week Sprints**
    - Sprint length: 2 weeks (~25 h)
    - Sprint Planning: Select and estimate 2–3 stories at the start of each sprint
    - Sprint Review & Retrospective: Brief reflection and process adjustments at the end of each sprint
- **Definition of Done (DoD)**
    - Criteria per story:
        - Functional code compiles successfully
        - Basic documentation and code comments are updated
        - Example script demonstrates the functionality
        - Issue in backlog marked as “Done”
- **Sprint Retrospective**
    - Short retrospective (max. 15 min) after each sprint:
        - What went well?
        - Where were the blockers?
        - What improvements will we carry into the next sprint?
        - Feedback
        - Planning new tasks for next sprint
- **Meeting Structure**
    - Bi-weekly Sprint Reviews: Every two weeks, a review session is held to evaluate progress, demonstrate implemented features, and plan the next sprint based on feedback
    - Weekly Check-in: Short status meetings take place in the alternating weeks to provide updates, discuss blockers, and align with the supervisor


## Resources

+ Technical References
    + ARGoS
        + [ARGoS: a modular, parallel, multi-engine simulator for multi-robot systems](https://doi.org/10.1007/s11721-012-0072-5)
    + PettingZoo Parallel API
        + https://pettingzoo.farama.org/api/parallel/
        + https://arxiv.org/pdf/2009.14471
    + Ray RLlib
        + https://docs.ray.io/en/latest/rllib/index.html
        + https://docs.ray.io/en/latest/rllib/multi-agent-envs.html
        + https://docs.ray.io/en/latest/rllib/external-envs.html
    + ZeroMQ
        + https://zeromq.org/
+ Research
    + [Reinforcement learning for swarm robotics: An overview of applications, algorithms and simulators](https://doi.org/10.1016/j.cogr.2023.07.004)
    
