# ARGoS-PettingZoo Bridge

**A high-performance interface for Multi-Agent Reinforcement Learning in swarm robotics simulation**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PettingZoo](https://img.shields.io/badge/PettingZoo-Parallel%20API-green.svg)](https://pettingzoo.farama.org/)
[![ARGoS3](https://img.shields.io/badge/ARGoS-3.0-orange.svg)](https://www.argos-sim.info/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

This project provides a **bidirectional communication bridge** between the [ARGoS](https://www.argos-sim.info) multi-robot simulator and Python-based Multi-Agent Reinforcement Learning (MARL) frameworks. By exposing ARGoS as a [PettingZoo](https://pettingzoo.farama.org/) Parallel Environment, researchers can leverage state-of-the-art RL libraries (RLlib, Stable-Baselines3, CleanRL) while benefiting from ARGoS's physically accurate swarm simulation.

### Research Motivation

Swarm robotics research requires simulators that balance **physical fidelity** with **computational efficiency**. While ARGoS excels at realistic multi-robot physics, its C++ architecture creates barriers for ML researchers accustomed to Python ecosystems. This bridge eliminates that barrier through:

- **Zero-copy observation batching** via ZeroMQ IPC
- **Deterministic stepping** with seed-controlled reproducibility
- **Task-agnostic design** separating simulation from reward logic

### Key Features

| Feature | Description |
|---------|-------------|
| **PettingZoo Compliance** | Full Parallel API compatibility for seamless RL library integration |
| **Batched Communication** | Single ZeroMQ socket handles all agents (~50ms latency at 20 agents) |
| **Modular Rewards** | External callback architecture for custom reward shaping |
| **Reproducibility** | Deterministic seeding with simulator restart for exact trajectory replay |
| **Scalability** | Validated up to 50 agents with constant per-step latency |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Concept](docs/concept.md) | Research vision and theoretical background |
| [Architecture](docs/architecture.md) | Technical specification, API reference, wire protocol |
| [How to Run](docs/how-to-run.md) | Installation, configuration, execution guide |
| [Tests](docs/tests.md) | Test suite documentation and CI/CD |
| [Logging](docs/logging.md) | Debug logging configuration |
| [Results](docs/results.md) | Experimental results and analysis |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Python Process                                 │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────────┐   │
│  │   RL Algorithm  │───▶│    ArgosEnv      │───▶│   reward_fn callback  │   │
│  │  (RLlib, SB3)   │    │  (PettingZoo)    │    │  (aggregation, etc.)  │   │
│  └─────────────────┘    └────────┬─────────┘    └───────────────────────┘   │
│                                  │ ZeroMQ REQ                               │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │ JSON/TCP
┌──────────────────────────────────┼──────────────────────────────────────────┐
│                                  ▼ ZeroMQ REP                               │
│                           ARGoS3 Simulator (C++)                            │
│  ┌─────────────────────┐    ┌─────────────────┐    ┌────────────────────┐   │
│  │  zoo_loop_functions │◀──▶│  Foot-Bot Agent │◀──▶│  Physics Engine    │   │
│  │  (observation batch)│    │  (controller)   │    │  (dynamics2d)      │   │
│  └─────────────────────┘    └─────────────────┘    └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Communication Protocol:**
- **Request** (Python → C++): `{"command": "step", "payload": {"actions": {"robot_0": "forward_speed", ...}}}`
- **Response** (C++ → Python): `{"observations": {"schema": "compact_v1", "agents": [...], "proximity": [[24 floats], ...], "position": [[x,y,z], ...]}}`

For complete protocol specification, see [Architecture Documentation](docs/architecture.md#wire-protocol-specification).

---

## Quick Start

### Prerequisites

```bash
# macOS
brew install argos3 zeromq cmake

# Ubuntu/Debian
sudo apt install argos3 libzmq3-dev cmake
```

### Installation

```bash
git clone https://github.com/tombackert/ArgosToZoo.git
cd ArgosToZoo

# Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install numpy gymnasium

# Build C++ plugins
mkdir build && cd build && cmake .. && make && cd ..
```

### Run Example

```bash
# Random policy baseline
PYTHONPATH=src python scripts/random_policy.py \
    --argos experiments/footbot_10.argos \
    --episodes 5 --steps 200 --seed 42

# RL smoke test (stateless REINFORCE)
PYTHONPATH=src python scripts/rl_smoke.py \
    --argos experiments/footbot_10.argos \
    --episodes 20 --steps 100 --seed 123
```

### Minimal Code Example

```python
from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward

env = ArgosEnv(
    argos_file="experiments/footbot_10.argos",
    max_steps=500,
    reward_fn=aggregation_reward,
    quiet=True,
)

obs, info = env.reset(seed=42)
for _ in range(500):
    actions = {agent: env.action_space(agent).sample() for agent in env.agents}
    obs, rewards, terms, truncs, infos = env.step(actions)
    if all(truncs.values()):
        break
env.close()
```

---

## Performance

Benchmarks on Apple M1 Pro, headless mode, 20Hz simulation tick rate:

| Agents | Mean Latency | P95 Latency | Payload Size |
|--------|--------------|-------------|--------------|
| 5      | 49.99 ms     | 50.90 ms    | 0.47 KB      |
| 10     | 49.98 ms     | 51.00 ms    | 0.94 KB      |
| 20     | 49.99 ms     | 50.80 ms    | 1.88 KB      |

Latency remains constant as agent count increases; dominated by simulation tick rate rather than communication overhead.

---

## Project Structure

```
ArgosToZoo/
├── src/
│   ├── plugin/                 # C++ ARGoS components
│   │   ├── controllers/        # Per-robot IPC controller
│   │   └── loop_functions/     # ZeroMQ server, observation batching
│   └── zoo/                    # Python package
│       ├── argos_env.py        # PettingZoo ParallelEnv implementation
│       ├── zmq_client.py       # ZeroMQ client with retry/recovery
│       └── scenarios/          # Reward function callbacks
├── experiments/                # ARGoS configuration files
│   ├── footbot_{1,5,10,20}.argos
│   └── visual/                 # Configurations with Qt visualization
├── scripts/                    # Training and evaluation utilities
│   ├── random_policy.py        # Baseline random agent
│   ├── rl_smoke.py             # REINFORCE learning signal test
│   └── ray_footbot_aggregation.py  # RLlib PPO training
├── tests/                      # Pytest test suite
└── docs/                       # Comprehensive documentation
```

---


## Spaces and Actions

### Observation Space

```python
Dict({
    "proximity": Box(low=0.0, high=1.0, shape=(24,), dtype=float32),  # IR sensors
    "position": Box(low=-inf, high=inf, shape=(3,), dtype=float32),   # [x, y, z]
})
```

### Action Space

```python
Discrete(5)  # {0: stop, 1: forward, 2: backward, 3: turn_left, 4: turn_right}
```

---

## Integration with RL Libraries

### RLlib

```python
from ray.rllib.algorithms.ppo import PPOConfig
from ray.tune.registry import register_env
from zoo.argos_env import ArgosEnv
from zoo.scenarios.aggregation import aggregation_reward

def env_creator(cfg):
    return ArgosEnv(argos_file=cfg["argos_file"], reward_fn=aggregation_reward, quiet=True)

register_env("argos", lambda cfg: env_creator(cfg))
config = PPOConfig().environment("argos", env_config={"argos_file": "experiments/footbot_10.argos"})
algo = config.build()
```

---

## Citation

If you use this software in academic work, please cite:

```bibtex
@software{argostozoo2025,
  author       = {Backert, Tom},
  title        = {{ARGoS-PettingZoo Bridge}: A High-Performance Interface for
                  Multi-Agent Reinforcement Learning in Swarm Robotics},
  year         = {2025},
  url          = {https://github.com/tombackert/ArgosToZoo}
}
```

### Related Work

- **ARGoS Simulator**: Pinciroli, C., et al. (2012). *ARGoS: A Modular, Parallel, Multi-Engine Simulator for Multi-Robot Systems.* Swarm Intelligence, 6(4), 271-295.
- **PettingZoo**: Terry, J., et al. (2021). *PettingZoo: Gym for Multi-Agent Reinforcement Learning.* NeurIPS.

---

## Contributing

1. Fork and create a feature branch: `git checkout -b feature/your-feature`
2. Write tests first (see [tests documentation](docs/tests.md))
3. Validate: `flake8 src/zoo && PYTHONPATH=src pytest tests/ -v`
4. Submit PR with documentation updates if API changes

---

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

*Developed as part of a Bachelor's thesis on Multi-Agent Reinforcement Learning for Swarm Robotics at the University of Lübeck.*
