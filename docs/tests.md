[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md) | [Results](results.md) | [Backlog](backlog.md)

# Test & CI Documentation

This document enumerates the automated tests, their intent, and the CI pipeline that enforces repository quality. It serves as a reproducibility reference for the bachelor thesis.

## Test Philosophy

1. Correctness: Validate PettingZoo API contract, observation/action mapping, and reward shaping.
2. Determinism: Stable trajectories under fixed seed & action sequences.
3. Resilience: Graceful handling of timeouts, socket recovery, and shutdown.
4. Signal Quality: Reward variance proves non‑degenerate learning signal.
5. Maintainability: Each new feature accompanied by a focused test.

## Test Inventory (Pytest)

| File | Focus | Key Assertions |
|------|-------|----------------|
| `test_env.py` | Core env behavior | Reset/step lifecycle; observation shapes; action validation |
| `test_parallel_api.py` | PettingZoo compliance | Passes `parallel_api_test` semantics (agents list clearing, trunc/term mapping) |
| `test_metrics_reward.py` | Reward function unit tests | Aggregation reward callback correctness; metric computation |
| `test_reward_variance.py` | Shaping variability | Variance > 0 over sampled steps (guards regression to constant reward) |
| `test_seed_layout.py` | Determinism & reseeding | Same seed → identical positions; different seed → different layout |
| `test_seed_positions_multi.py` | Multi-agent seed positions | Position reproducibility across multiple agents |
| `test_timeout_recovery.py` | ZMQ recovery | Induced timeout triggers reconnect then successful further steps |
| `test_graceful_shutdown.py` | Resource cleanup | Multiple `close()` idempotent; no zombie subprocess detected |
| `test_logging.py` | Logging surface | Level filtering and JSON/text formatting basic sanity |
| `test_legacy_removal.py` | API cleanup | Removed legacy parameters raise appropriate errors |

All tests are intentionally lightweight; heavy performance benchmarks live in scripts.

## Selective Running

Fast (logic only) exclude slower network/recovery tests:
```bash
pytest -k "not timeout and not graceful" -q
```

Full suite:
```bash
pytest -q
```

PettingZoo official parallel API test (redundant but explicit):
```bash
python -m pettingzoo.test.parallel_api_test zoo.argos_env:ArgosEnv
```

## Seeding Contract

`env.reset(seed=s)` restarts ARGoS when the underlying simulator requires a fresh process to apply a new random seed. Determinism guarantee: same seed + identical action sequence → identical reward/observation tensors for N steps (floating point tolerance). Covered by `test_seed_layout.py` and `test_seed_positions_multi.py`.

## Timeout & Recovery

Failure injection: artificially delay or drop a reply so Python REQ socket hits poll timeout. Recovery path recreates socket, performs a ping handshake, and resumes step loop without restarting ARGoS. Assertions ensure subsequent rewards flow and counters advance.

## Reward Variance Rationale

Ensures shaping not accidentally neutralized (e.g., coefficient set to 0, distance metric bug). Test samples multiple steps with random actions and asserts variance above a small epsilon.

## CI Pipeline Overview

Triggered via GitHub Actions (workflow file referenced as `.github/workflows/ci.yml`). Two tiers:

| Scenario | Job | Steps |
|----------|-----|-------|
| Feature branch push | fast-python | Install Python deps → flake8 → pytest (ARGoS-dependent tests auto-skip if plugin absent) |
| PR to `main` / push to `main` | full-integration | Brew deps → build & cache ARGoS → build plugin → clang-format check → full pytest |

### Caching

ARGoS build dir cached by hash of `CMakeLists.txt` + dependencies. Cache hit drastically reduces compile time in PR validation.

### Local Reproduction (full integration)
```bash
brew install pkg-config cmake libpng freeimage qt freeglut lua docbook asciidoc graphviz doxygen zeromq cppzmq clang-format
git clone https://github.com/ilpincy/argos3.git
cd argos3 && mkdir build && cd build
cmake -DCMAKE_CXX_STANDARD=17 ../src && make -j$(sysctl -n hw.ncpu) && sudo make install
cd ../../
pip install -r requirements.txt
pytest -q
```

### Linting

- `flake8` enforces Python style
- C++ formatting via `clang-format`

#### C++
Run for lint-checking a file:
```
clang-format -n --Werror src/plugin/loop_functions/zoo_loop_functions.cpp
```

Run for auto-fix a file:
```
clang-format -i src/plugin/loop_functions/zoo_loop_functions.cpp
```

#### Python
Lint-check a specific file:
```
flake8 src/zoo/argos_env.py
```

#### Pre Commit 
Run locally before committing:
```bash
flake8 src/zoo scripts tests
clang-format -i $(git ls-files 'src/plugin/loop_functions/*.[ch]pp' 'src/plugin/loop_functions/*.[ch]' 'src/plugin/controllers/*.[ch]pp' 'src/plugin/controllers/*.[ch]')
```

## Adding New Tests

1. Name file `test_<topic>.py` under `tests/`.
2. Use fixtures in `conftest.py` for env creation to avoid duplication.
3. Keep runtime < 1s where possible; mark long tests with `@pytest.mark.slow` (future filtering).
4. Update this document if the test validates a novel contract.

## Failure Triage Cheat Sheet

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Seed test mismatch | Non-deterministic simulator change | Re-check action gating; confirm single tick per step |
| Timeout recovery fail | Protocol change / handshake mismatch | Inspect loop DEBUG logs (`ARGOS_LOOP_LOG_LEVEL=DEBUG`) |
| Reward variance zero | Reward formula regression | Inspect loop functions implementation & recent commits |
| Graceful shutdown hangs | Subprocess still alive | Ensure close drains pipes & sets internal `_closed` flag |
| Parallel API test fail | Agent list not cleared | Verify `agents` empty after all terminations |

## Coverage Gaps / Future

* Performance regression test (steps/sec across agent counts).
* Sensor expansion tests (new arrays appended to schema).
* Optional fuzz test for malformed JSON recovery.
