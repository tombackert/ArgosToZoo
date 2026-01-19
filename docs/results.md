[Home](../README.md) | [Concept](concept.md) | [Architecture](architecture.md) | [How to Run](how-to-run.md) | [Tests](tests.md) | [Logging](logging.md) | [Project Management](project-management.md) | [Resources](resources.md) | [Results](results.md) | [Backlog](backlog.md)

# Results: Aggregation

## Aggregation Metrics
Metrics are computed in Python (not part of observations) and surfaced each step in `infos[agent]['metrics']`:

| Metric | Meaning |
|--------|---------|
| `centroid` | `[x,y,z]` centroid of all robot positions |
| `cohesion_mean` | Mean distance to centroid (aggregation radius) |
| `delta_cohesion` | Previous cohesion_mean minus current (improvement > 0) |
| `moved_mean` | Mean per-agent XY distance moved since last step |
| `max_prox` | Maximum proximity reading across all agents (collision proxy) |
| `polarization` | Placeholder (0.0; future heading alignment) |
| `success` | True after cohesion_mean < 0.25 for 20 consecutive steps |

Aggregation reference formula (implemented in `zoo/scenarios/aggregation.py`): `r = w_coh*Δcohesion - w_col*max_prox + w_move*moved_mean` (first step forced 0.0). These weights are function arguments, not environment constructor params. Provide the callback via `ArgosEnv(..., reward_fn=aggregation_reward)`.


## Scenario

The training scenario for aggregation experiments lives at `experiments/footbot_10.argos`.

Key properties:

* 10 Foot-Bots in a 6m x 6m arena, tick rate = 20 Hz.
* Initial poses are randomized **inside the loop functions** with a minimum center-to-center spacing of 0.2 m (attempts up to 500 trials per robot before giving up — remaining robots retain template positions if packing fails).
* Randomization is **deterministic**: the ARGoS `<experiment random_seed=...>` together with the internal RNG drives placement. Resetting the environment with the same seed reproduces identical layouts.
* Headless (no `<visualization>` block) for faster RL training throughput.

## Seeding & Determinism (How It Works)

Deterministic layouts require controlling *both* the ARGoS world RNG and the Python-side RNG used in experiments.

Pipeline when you call `env.reset(seed=S)`:

1. A temporary copy of the original `.argos` file is created with `<experiment random_seed="S"/>`.
2. The ARGoS simulator process is **restarted** with that temp file (always, even if the same seed is reused, to guarantee a clean RNG state).  
3. Inside `CZooLoopFunctions::Init()` (and again on reset) we call `RandomizeStartPositions()`, which samples positions & orientations via `CRandom::CreateRNG("argos")`. Because ARGoS was seeded with `S`, the sampled sequence is identical for identical `S`.
4. Minimum center-to-center separation constraint: candidates rejected if distance < 0.2 m; up to 500 trials per robot. (If packing fails late, remaining robots keep the placeholder grid position—rare at this density.)
5. Python sets `env.np_random = default_rng(S)` for any downstream stochastic policies you write.

Important nuances:

* Calling `reset()` **without a seed** does NOT restart the process; the placement will be re-randomized using the *continuing* RNG stream (different layout). Provide the seed every episode you want reproduced.
* Identical seed → identical ordered list of robot positions and orientations; reward & observation trajectories remain identical for a deterministic policy.
* Change the seed → new layout; all else constant.

Quick reproducibility check (run twice, identical output expected):

```bash
PYTHONPATH=src python scripts/run_footbot10.py --seed 123 --steps 1
```

## Training Setup

|      |     |
|------|-----|
| Scenario  | Aggregation |
| Algorithm | PPO         |

The script `ray_footbot_aggregation.py` implements a short training script to train the aggregation behavior. It uses Ray RLlib's implementation of PPO.

## Training Result

[Short clip of end result]