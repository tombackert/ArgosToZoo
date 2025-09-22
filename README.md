[Home](README.md) | [Concept](docs/concept.md) | [Architecture](docs/architecture.md) | [How to Run](docs/how-to-run.md) | [Tests](docs/tests.md) | [Logging](logging.md) | [Project Management](docs/project-management.md) | [Resources](docs/resources.md) | [Results](docs/results.md) | [To be Done](docs/things-to-be-done.md)

# ArgosToZoo

High‑performance bridge between the [ARGoS](https://www.argos-sim.info) swarm robotics simulator (C++) and modern Multi‑Agent RL tooling in Python (PettingZoo).

> Goal: Run physically realistic swarm experiments while writing learning logic purely in Python.

> Proof of concept: Run a 10 agents aggregation scenario. 

## Documentation Hub

| Topic |
|-------|
| [Vision](docs/concept.md) | 
| [Architecture](docs/how-to-run.md) |
| [How to Run](docs/how-to-run.md) |
| [Logging](docs/logging.md) |
| [Tests & CI](docs/tests.md) |
| [Project Management](docs/project-management.md) |
| [Resources](docs/resources.md) |
| [Results](docs/results.md) |
| [To be Done](docs/things-to-be-done.md) |

## Overview

| Aspect | Summary |
|--------|---------|
| Data Path | Batched REQ/REP (single ZeroMQ socket) each tick: Python sends all actions → C++ returns task‑agnostic observations (reward computed in Python callback) |
| Action Space | Uniform discrete mapping (stop, forward, backward, turn_left, turn_right) |
| Observation Schema | Compact array format (`compact_v1`) with proximity (24) + positions (no rewards in wire payload) |
| Reward Shaping | External `reward_fn` callback (e.g. `aggregation_reward`); default env reward is constant 0.0 |
| Determinism | One simulator tick per `env.step()`; seeding restarts ARGoS with fixed seed |
| Scaling Proven | Benchmarked up to 50 agents with constant latency (~50ms @ 20Hz tick) |

See the *architecture* doc for rationale, extensibility model, and performance table.
For full setup, multi‑episode random policy, and RL smoke test refer to *How to run* section.

## Repository Map

```
src/plugin/        # C++ ARGoS controller + loop functions (ZeroMQ REP server)
src/zoo/           # Python PettingZoo parallel env + ZMQ client
src/zoo/scenarios  # Reward functions for training
experiments/       # .argos scenario files (1,5,10,20 foot-bots)
scripts/           # Utilities: random_policy, rl_smoke, manual_control
tests/             # Pytest suite: API, seeding, reward variance, recovery, shutdown
docs/              # Modular documentation (see links above)
```

## Contributing to this project

1. Branch: `git checkout -b feature/<name>`
2. Add/adjust tests first (see `docs/tests.md`).
3. Run `flake8 src/zoo && pytest -q`.
4. Commit & push; review CI (fast Python job). Open PR for full integration run.
5. Update docs if public API / behavior changes.

Full workflow & CI details in `docs/tests.md`.

## Resources

ARGoS paper, PettingZoo API, RLlib multi-agent docs, ZeroMQ guide, and relevant swarm RL literature are linked inside the concept & architecture documents or in the [Resouces section](docs/resources.md) for academic citation convenience.

## Citation / Thesis Note

This repository forms the foundation for a bachelor thesis; architectural and experimental changes should keep the docs in sync to preserve academic reproducibility (update affected doc section in same PR).

For deep dives start with: Concept → Architecture → How to Run → Tests → Logging.

