[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md) | [Results](results.md) | [Backlog](backlog.md)

# Logging Guide

Unified, minimal, and optionally structured logging across Python and C++ components for debugging, benchmarking, and reproducibility.

## Goals

* Fast toggle between silent CI mode and verbose dev mode.
* Consistent level names across languages.
* Optional JSON for machine ingestion / later analysis.
* Explicit control of simulator (loop) vs. per‑robot controller noise.

## Python Environment Logging

Constructor parameters on `ArgosEnv`:
```python
ArgosEnv(
  argos_file: str,
  log_level: str = 'INFO',        # DEBUG/INFO/WARN/ERROR
  log_format: str = 'text',       # 'text' or 'json'
  quiet: bool = False,            # overrides to ERROR if True
  controller_log_level: str|None = None,  # forwarded to C++
  loop_log_level: str|None = None,        # forwarded to C++
)
```

Behavior:
* Invalid `log_level` / `log_format` -> `ValueError` (fail fast).
* `quiet=True` forces environment logger to ERROR regardless of `log_level`.
* Structured JSON lines: `{`"ts": ISO8601 UTC, "level": ..., "msg": ..., <extra fields>}`.

Example:
```python
env = ArgosEnv('experiments/footbot_10.argos', log_level='DEBUG', loop_log_level='DEBUG')
```

## C++ Logging (Controllers & Loop Functions)

Configured via environment vars (evaluated at simulator launch):

| Component | Env Var | Default | Notes |
|-----------|---------|---------|-------|
| Controller (per robot) | `ARGOS_CONTROLLER_LOG_LEVEL` | INFO | DEBUG prints action transitions |
| Loop Functions (global) | `ARGOS_LOOP_LOG_LEVEL` | INFO | DEBUG prints ZMQ state + payload summaries |

Accepted: `DEBUG`, `INFO`, `WARN`, `ERROR` (case‑insensitive; invalid -> INFO fallback).

Shell example:
```bash
ARGOS_CONTROLLER_LOG_LEVEL=ERROR ARGOS_LOOP_LOG_LEVEL=DEBUG \
  argos3 -c experiments/footbot_10.argos
```

Through Python (preferred):
```python
env = ArgosEnv('experiments/footbot_10.argos', controller_log_level='ERROR', loop_log_level='DEBUG')
```

## ZMQ Diagnostics (Loop DEBUG)

One line per tick, e.g.:
```
ZMQ status phase=PendingRequest pending=yes total_req=42 total_rep=42 idle_ticks=0
```
Meaning:
* phase – high level socket state (WaitingForFirstRequest, PendingRequest, Idle)
* pending – whether a request was waiting at tick boundary
* totals – cumulative counters (req/rep symmetry check)
* idle_ticks – consecutive ticks without client request

## Usage Recipes

| Goal | Command / Code |
|------|----------------|
| All debug | `ArgosEnv(..., log_level='DEBUG', loop_log_level='DEBUG', controller_log_level='DEBUG')` |
| Loop only debug | `loop_log_level='DEBUG', controller_log_level='ERROR'` |
| JSON structured | `log_format='json'` |
| Max silence (CI) | `quiet=True` + set `ARGOS_*_LOG_LEVEL=ERROR` |
| Inspect ZMQ phases | loop log level DEBUG |

## Error / Edge Behavior

| Scenario | Result |
|----------|--------|
| Bad `log_level` | Exception (Python) / fallback INFO (C++) |
| Bad `log_format` | Exception |
| `quiet=True` + level provided | ERROR enforced |
| Proximity length mismatch | Single WARN then pad/truncate |
| Missing actions payload | Loop WARN (first tick / lag) |

## Sample JSON Output
```json
{"ts":"2025-08-19T07:15:12.145623Z","level":"DEBUG","msg":"ZMQClient initialized","port":"5555","timeout_ms":5000}
```

## Future Improvements
* Correlation IDs (episode, step) auto-injected.
* Bridge to Python `logging` handlers.
* Structured C++ logs mirrored as JSON via an optional flag.

Return to: [Documentation Hub](../README.md).
