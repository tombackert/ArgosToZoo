Plan of Milestone 3 so that within ~50h we achieve a visible, measurable POC with **10 agents**. We take **Aggregation** as the default goal (easiest entry), **Flocking** as the stretch goal.

# Goal & “Definition of Success”

* **Task (Default): Aggregation** – The 10 bots form a compact cluster within an episode.
* **Success criterion:** Mean distance to the centroid < **R_thr** for ≥ **T_hold** steps (e.g. R_thr = 0.6 m, T_hold = 200 ticks).
* **Stretch (optional): Flocking** – Additionally high alignment polarization **P > 0.7** with similar compactness.

# Scenario in ARGoS (10 Foot-Bots)

* **Arena:** Circle or square without obstacles, light domain randomization (start positions/orientations).
* **Tick rate:** Keep 20 Hz; **headless** (no Qt viewer) for training.
* **Reset:** Uniform random initial distribution with minimum spacing (e.g. >0.2 m), seeds reproducible.

# Observations & Actions

* **Observation (initial minimal):** 24-dim proximity array (already present).
  *(No global state leak, partial observability preserved.)*
* **Action space (discrete, parameter-sharing friendly):**
  `0: forward`, `1: turn_left`, `2: turn_right`, `3: stop`
  *(Optional 5-actions: +`backward` for flocking fine-tuning.)*
* **Timing:** Apply actions at *T+1* (already done).

# Rewards (task-specific via callback)

Reward shaping is implemented *exclusively* in a Python callback (`reward_fn`). The environment itself supplies only observations. The provided aggregation reference callback (`aggregation_reward`) uses a **team** reward formula:

```
r_team = w_coh * Δcohesion - w_col * max_prox + w_move * moved_mean
```

Definitions:
* `cohesion_mean` = mean distance to centroid (lower better); `Δcohesion = prev - current` (improvement > 0).
* `max_prox` = maximum proximity sensor value across agents (collision / spacing proxy).
* `moved_mean` = mean per‑agent displacement since previous step.
* `success` flag when cohesion_mean < R_thr for T_hold consecutive steps (exposed as metric; any episodic bonus handled inside callback if desired).

Example weights used in early experiments (purely callback arguments, **not** env constructor params): `w_coh=1.0`, `w_col=0.5`, `w_move=0.05`.

Usage:
```python
from zoo.scenarios.aggregation import aggregation_reward
env = ArgosEnv("experiments/footbot_10.argos", reward_fn=aggregation_reward)
```

To explore variants just wrap or fork the callback; no change to `ArgosEnv` required.

**Flocking add-on (stretch):**

```
r_align = w_align * polarization_t
```

with polarization `P = |(1/N) Σ v_i/||v_i|| |` (derive velocity/heading from loop).

# Algorithm & Training Setup

* **Policy sharing:** **One** shared PPO policy for all agents (parameter sharing).
* **Baseline:** Heuristic (Boids-like: repulsion/align/cohesion from proximity) as comparison.
* **Framework:** RLlib (simple multi-agent mapping), or TorchRL if you want leaner.
* **PPO initial hyperparameters (robust & conservative):**

  * `gamma=0.99`, `gae_lambda=0.95`, `clip_param=0.2`
  * `entropy_coeff=0.01` (gegen Premature Convergence)
  * `lr=3e-4`, `vf_clip_param=10.0`
  * `train_batch_size=32768`, `sgd_minibatch_size=2048`, `num_sgd_iter=10`
  * `rollout_fragment_length=200`, `framework=torch`
* **Parallelization:** 2–4 parallel env processes (more may add little at 20 Hz). Headless + reduced render cost.
* **Logging:** TensorBoard (return, success rate, cohesion/polarization curves). Episode videos only for samples (eval runs).

# Metrics & Evaluation (automated in the loop)

* **Cohesion:** `mean ||pos_i - centroid||` per step + moving average.
* **Success rate:** Fraction of episodes that satisfy the criterion.
* **Collisions proxy:** Mean `max_proximity` per step.
* **(Stretch) Polarization:** P in [0,1].

> Do not put these metrics into the observation; only for reward/eval.

# Experiment Matrix (lightweight)

1. **R-shaping:** (A) as above, (B) stronger collision penalty, (C) without move bonus.
2. **Action set:** 4-actions vs. 5-actions.
3. **Algorithm:** PPO-shared vs. (stretch) MAPPO/centralized value.
  → 3–5 short runs of 200–300k steps, best setup then to 1–1.5M steps.

# Baseline (heuristic)

* **Aggregation heuristic:**

  * Wenn hohe frontale Proximity → leichte Drehung weg; sonst **leicht** zur stärksten freien Richtung drehen + vorwärts.
  * Optional: “Random Walk” Noise ε=0.05.
* **Goal:** Show RL > heuristic with same sensing (success rate / cohesion).

# Artifacts/Deliverables (DoD for M3)

* `experiments/footbot_10.argos` (reset randomization, headless ready)
* `src/zoo/argos_env.py` (10 agents stable, seeds, info metrics)
* `scripts/train_aggregation_rllib.py` (PPO-shared, TB logging)
* `scripts/baseline_aggregation.py` (heuristic)
* `eval/metrics.py` (cohesion, polarization, success check)
* `reports/m3_results.md` with 2–3 plots (return, cohesion), 1 short GIF/video
* CI job that runs smoke-train (short, 1–2k steps) + unit eval

# GitHub Issues (suggested)

* **M3-01:** Arena & reset randomization for 10 bots
* **M3-02:** Reward: Cohesion Δ + collision + move; loop-side metrics
* **M3-03:** PPO training script (RLlib), policy-sharing mapping
* **M3-04:** TensorBoard + checkpointing + eval hook (success rate)
* **M3-05:** Heuristic baseline + shared evaluator
* **M3-06:** Plots & report (m3_results.md) + GIF export
* *(Stretch)* **M3-S1:** Flocking reward (polarization) + action-5
* *(Stretch)* **M3-S2:** Centralized value / MAPPO variant

# Timeline (≈50 h, 6 weeks)

* **W1 (8h):** Arena + reset + metrics in loop, implement reward A
* **W2 (10h):** RLlib PPO script, policy sharing, TB logging
* **W3 (10h):** First runs (≤300k steps), debug, light hyperparam tuning
* **W4 (8h):** Heuristic baseline + shared evaluator
* **W5 (8h):** Longer run (≈1M steps) + stability checks
* **W6 (6h):** Plots, short clip, m3_results.md, cleanup & README update

# Small Implementation Snippets (sketchy)

**Policy mapping (RLlib):**

```python
def policy_mapping_fn(agent_id, *args, **kwargs):
    return "shared_policy"

config = {
    "env": "ArgosEnvWrapper",
    "multiagent": {
        "policies": {"shared_policy": (None, obs_space, act_space, {})},
        "policy_mapping_fn": policy_mapping_fn,
    },
    "framework": "torch",
    "gamma": 0.99,
    "lr": 3e-4,
    "clip_param": 0.2,
    "entropy_coeff": 0.01,
    "train_batch_size": 32768,
    "sgd_minibatch_size": 2048,
    "num_sgd_iter": 10,
    "rollout_fragment_length": 200,
}
```

**Eval hook (success rate):**

* Per episode in `info["metrics"]` from the loop: `cohesion_mean`, `success_bool`.
* RLlib `evaluation_interval=1`, `custom_eval_function` -> log success rate.
