[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md)

# Project Management

This document documents the organisational steps and milestones in order to reach the end goal of the project.

## 🏁 Milestones

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

## 🌀 Agile Approach

- **Product Backlog & Stories:** Kanban board (GitHub Issues)
- **Two-Week Sprints (~25 h):** Plan, review, retrospectives
- **Definition of Done:** Code compiles, docs updated, example works, issue closed
- **Meeting Structure:** Bi-weekly reviews & weekly check-ins


Return to: [Documentation Hub](../README.md).