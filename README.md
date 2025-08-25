# ArgosToZoo

High‑performance bridge between the [ARGoS](https://www.argos-sim.info) swarm robotics simulator (C++) and modern Multi‑Agent RL tooling in Python (PettingZoo).

> Goal: Run physically realistic swarm experiments while writing learning logic purely in Python.

> Proof of concept: Run a 5 agents 

## Quick Links (Documentation Hub)

| Topic |
|-------|
| [Concept / Vision](docs/concept.md) | 
| [Architecture & Developer Guide](docs/how-to-run.md) |
| [How to Run (Setup & E2E)](docs/how-to-run.md) |
| [Logging (Python & C++)](docs/logging.md) |
| [Tests & CI](docs/tests.md) |
| [Project Management](docs/project-management.md) |
| [Resources](docs/resources.md) |

## Overview

| Aspect | Summary |
|--------|---------|
| Data Path | Batched REQ/REP (single ZeroMQ socket) each tick: Python sends all actions → C++ returns all observations & rewards |
| Action Space | Uniform discrete mapping (stop, forward, backward, turn_left, turn_right) |
| Observation Schema | Compact array format (`compact_v1`) with proximity (24), positions, per‑agent rewards |
| Reward Shaping | `distance_xy - 0.5 * max_proximity` (first step = 0.0) |
| Determinism | One simulator tick per `env.step()`; seeding restarts ARGoS with fixed seed |
| Scaling Proven | Benchmarked up to 20 agents with constant latency (~50ms @ 20Hz tick) |

See the architecture doc for rationale, extensibility model, and performance table.

## 60‑Second Quick Start (macOS)

```bash
# deps (abbrev) – full list in docs/how-to-run.md
brew install pkg-config cmake zeromq cppzmq libpng freeimage qt freeglut lua docbook asciidoc graphviz doxygen clang-format
pip install -r requirements.txt

# build plugin
rm -rf build && mkdir build && cd build && cmake .. && make -j$(sysctl -n hw.ncpu) && cd ..

# smoke test (5 agents, 3 steps)
PYTHONPATH=src python - <<'PY'
from zoo.argos_env import ArgosEnv
env = ArgosEnv('experiments/footbot_5.argos', loop_log_level='WARN', controller_log_level='ERROR')
obs, info = env.reset(seed=0)
for _ in range(3):
    obs, rew, term, trunc, info = env.step({a:0 for a in env.agents})
    print({a: float(rew[a]) for a in rew})
env.close()
PY
```

For full setup, multi‑episode random policy, and RL smoke test refer to `docs/how-to-run.md`.

## Repository Map (Essentials)

```
src/plugin/        # C++ ARGoS controller + loop functions (ZeroMQ REP server)
src/zoo/           # Python PettingZoo parallel env + ZMQ client
experiments/       # .argos scenario files (1,5,10,20 foot-bots)
scripts/           # Utilities: random_policy, rl_smoke, manual_control
tests/             # Pytest suite: API, seeding, reward variance, recovery, shutdown
docs/              # Modular documentation (see links above)
```

## Contributing (Short Form)

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

---

For deep dives start with: Concept → Architecture → How to Run → Tests → Logging.
