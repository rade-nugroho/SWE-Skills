# Reliability

Use this when a task has a reliability or availability target, when you need to turn such a target into numbers (downtime budget, MTTR budget, failure intensity), or when deciding whether testing has made software reliable enough to release. For techniques that make a system tolerate faults (timeouts, retries, redundancy, failover), see [fault-tolerance.md](fault-tolerance.md); this file is about measuring and predicting reliability.

## Contents
1. Reliability metrics and formulas
2. Reliability testing
3. Software reliability growth models (SRGMs)
4. Practical use: fit, estimate, decide release
5. Source notes

## 1. Reliability metrics

| Metric | Meaning | Formula |
|---|---|---|
| Reliability `R(t)` | probability of no failure over `t` time of operation | constant rate: `R(t) = e^(−λt)` |
| Failure rate `λ` | failures per unit of operating time | `failures / total operating time`; constant rate: `MTTF = 1/λ` |
| MTTF | mean operating (up) time until a failure | `total uptime / failures` |
| MTTR | mean time to detect, repair and restore | `total downtime / failures` |
| MTBF | mean time from one failure to the next (repairable system) | `MTBF = MTTF + MTTR` |
| Availability `A` | fraction of time the system is usable | `A = MTTF / (MTTF + MTTR) = MTTF / MTBF` |
| ROCOF | rate of occurrence of failures (failure intensity) | failures per unit time in a window; for an NHPP model `λ(t) = dm(t)/dt` |
| POFOD | probability of failure on demand | `failed demands / total demands`; P(≥1 failure in `n` demands) `= 1 − (1 − p)^n` |

- Some ops tools use "MTBF" for mean up-time between failures (MTTF here) and write `A = MTBF / (MTBF + MTTR)`. Same idea; check which definition a dashboard uses before comparing.
- Match the metric to usage: POFOD for on-demand actions (a payment, a safety shutdown), ROCOF for continuously running services, availability when downtime matters more than failure count. Service SLOs are often request-based: `successful requests / valid requests`.
- Measure in execution (operating) time where possible; calendar time mixes in idle periods.
- Components in series (all needed): `A = A1·A2·…`. Redundant in parallel (any one suffices): `A = 1 − (1 − A1)(1 − A2)…`. That assumes independent failures, which is optimistic: shared dependencies, config and deploys fail together.

### Availability target → downtime budget

`allowed downtime = (1 − A) × period`

| A | per year | per month (30.4 d) | per week | per day |
|---|---|---|---|---|
| 99% | 3.65 d | 7.3 h | 1.68 h | 14.4 min |
| 99.5% | 1.83 d | 3.65 h | 50.4 min | 7.2 min |
| 99.9% | 8.77 h | 43.8 min | 10.1 min | 1.44 min |
| 99.95% | 4.38 h | 21.9 min | 5.04 min | 43.2 s |
| 99.99% | 52.6 min | 4.38 min | 60.5 s | 8.6 s |
| 99.999% | 5.26 min | 26.3 s | 6.05 s | 0.86 s |

Rearranged into engineering budgets:
- longest tolerable repair for a given failure rate: `MTTR ≤ MTTF · (1 − A) / A`
- failure rate needed for a given repair time: `MTTF ≥ MTTR · A / (1 − A)`, so `λ ≤ 1 / MTTF`

Example: 99.9% with a 30 min MTTR needs MTTF ≥ ~500 h (λ ≤ 0.002 failures/h, about one outage per 3 weeks). If that is unrealistic, shrinking MTTR (fast rollback, automated failover) is often cheaper than preventing failures.

### Demonstrating a target with zero failures

With `n` independent representative demands (or `T` hours) and no failures, the 95% upper bound is `p ≤ 3/n` (or `λ ≤ 3/T`), because `e^(−3) ≈ 0.05`. Showing POFOD ≤ 10⁻³ takes ~3,000 failure-free demands; λ ≤ 0.001/h takes ~3,000 failure-free hours. Targets around 10⁻⁶ and beyond cannot be shown by testing alone; they need design arguments (redundancy, formal methods).

## 2. Reliability testing

Goal: run the software under realistic conditions long enough to observe failures, measure the metrics above, and feed a growth model.

| Type | What it checks |
|---|---|
| Feature | each function works correctly and consistently under expected conditions |
| Regression | changes and fixes have not broken existing behavior or lowered reliability |
| Load | reliability at expected peak workload |
| Stress | behavior past the limits: where it breaks and whether it fails cleanly |
| Endurance (soak) | long runs: leaks, resource exhaustion, gradual slowdown |
| Volume | large data sets, tables, files |
| Recovery | restart and resume after crashes, kills, dependency loss; gives MTTR |

The work splits into three activities: **modelling** (predict from failure data), **measurement** (observe failures and uptime), **improvement** (fix causes, re-measure).

Plan:
1. **Objectives** — target metric and value from the NFR (e.g. λ ≤ 0.002/h, POFOD ≤ 10⁻³, 99.9%) and which severities count as failures.
2. **Operational profile** — the mix and frequency of real operations and inputs (from logs or analytics). Drive tests from it; otherwise measured intensity says little about production.
3. **Environment** — production-like config and data; automate so runs can last hours or days.
4. **Execute** — feature and regression first, then load, stress, endurance, recovery.
5. **Collect** data continuously (below).
6. **Analyze** — trend test, fit a model (section 4), look for failure patterns and root causes.
7. **Fix, retest, re-fit** until the target is met.

Data to collect, per failure:
- time in cumulative execution time (or test effort) since testing began → failure times `S_i` and inter-failure times `x_i = S_i − S_(i−1)`; or, if only counts are practical, failures per fixed interval → grouped data `(t_k, y_k)` with `y_k` cumulative
- severity, the underlying fault (count repeats of a known unfixed fault once), build, and when the fix landed
- down/up timestamps for MTTR and availability; demand counts for POFOD
- large code drops: growth models assume only fixes change the code, so a new feature batch starts a new data series

Inter-failure times feed JM, SW and quasi-renewal; failure times or grouped counts feed GO and PNZ.

## 3. Software reliability growth models

All assume failures get rarer as faults are found and fixed. Notation: `N` or `a` = initial (expected) fault count, `i` = failure index, `t_i` = time since failure `i−1`, `m(t)` = expected cumulative failures by `t`, `λ(t)` = failure intensity.

| Model | Class / data | Key assumptions | Params | Fits when |
|---|---|---|---|---|
| Jelinski-Moranda (1972) | finite-fault; times between failures | fixed `N` faults at start; each adds the same `φ` to the failure rate; each fault removed instantly and perfectly; rate constant between failures | `N, φ` | simple baseline; inter-failure times trend upward; tends to be optimistic |
| Schick-Wolverton (1978) | as JM | as JM, but hazard rises linearly with time since the last fix (Rayleigh inter-failure times) | `N, φ` | failures get more likely the longer a test cycle runs without one (testing intensifies within a cycle) |
| Goel-Okumoto (1979) | NHPP, finite; counts or failure times | detection rate proportional to faults remaining; constant per-fault rate `b`; perfect instant fixes; independent faults | `a, b` | default baseline; cumulative curve concave from the start (no slow ramp) |
| PNZ (1999) | NHPP; counts | S-shaped detection rate (testers learn); imperfect debugging: fault content grows linearly as fixes add faults | `a, b, α, β` | S-shaped cumulative curve, or one that keeps rising because fixes introduce faults; needs more data (4 params) |
| Quasi-renewal (Wang-Pham 1996) | counting process; inter-failure times | each inter-failure time is a scaled copy of the first, scale `α` per failure; distribution shape unchanged | `α` + params of `F₁` | inter-failure times grow by a roughly constant ratio; `α>1` growth, `α=1` ordinary renewal, `α<1` deterioration |

**Jelinski-Moranda**
- hazard in interval `i`: `λ(t_i) = φ(N − i + 1)`; `R(t_i) = e^(−φ(N−i+1)t_i)`; interval MTTF `= 1 / (φ(N−i+1))`
- after `n` failures: remaining faults `N − n`, current rate `φ(N − n)`
- MLE: `φ = n / Σ(N−i+1)x_i` and `Σ_{i=1..n} 1/(N−i+1) = n / (N − Σ(i−1)x_i / Σx_i)`. A finite `N̂` exists only if `Σ(i−1)x_i / Σx_i > (n−1)/2`, i.e. the data actually show growth.
- expected cumulative failures `m(t) = N(1 − e^(−φt))`, the same shape as GO

**Schick-Wolverton**
- hazard: `λ(t_i) = φ(N − i + 1) t_i`
- `R(t_i) = e^(−φ(N−i+1)t_i²/2)`; pdf `f(t_i) = φ(N−i+1) t_i e^(−φ(N−i+1)t_i²/2)`
- interval MTTF (Rayleigh mean) `= √(π / (2φ(N−i+1)))`
- MLE with `T = Σt_i²`: `Σ 1/(N−i+1) = φT/2` and `N = 2n/(φT) + Σ(i−1)t_i² / T`

**Goel-Okumoto**
- `dm/dt = b(a − m(t))` → `m(t) = a(1 − e^(−bt))`
- intensity `λ(t) = a·b·e^(−bt)` (= `b` × expected remaining faults); remaining faults `a − m(t) = a·e^(−bt)`
- reliability for the next `x` after `t`: `R(x|t) = e^(−[m(t+x) − m(t)]) = e^(−a(e^(−bt) − e^(−b(t+x))))`
- test time to reach target intensity `λ*`: `t* = ln(a·b / λ*) / b`
- MLE from failure times `S_1..S_n` (observed to `S_n`): `a = n / (1 − e^(−bS_n))` and `n/b = ΣS_i + n·S_n·e^(−bS_n) / (1 − e^(−bS_n))`. A finite `b̂` exists only if `ΣS_i < n·S_n/2` (failures cluster early). For grouped counts, maximize the Poisson likelihood (sketch below).
- rough band on cumulative failures: `m̂(t) ± z·√m̂(t)`

**PNZ (Pham-Nordmann-Zhang)**
- fault content `a(t) = a(1 + αt)`; `α` = fault introduction rate (fraction of `a` per unit time)
- detection rate `b(t) = b / (1 + βe^(−bt))`, S-shaped, from `b/(1+β)` up to `b`
- `dm/dt = b(t)(a(t) − m(t))` → `m(t) = a / (1 + βe^(−bt)) · [(1 − e^(−bt))(1 − α/b) + αt]`
- intensity `λ(t) = b(t)(a(t) − m(t))`; remaining faults `a(t) − m(t)`
- special cases: `α = 0` gives the inflection S-shaped model `a(1 − e^(−bt)) / (1 + βe^(−bt))`; `α = β = 0` gives GO

**Quasi-renewal**
- `X_n = α^(n−1) Z_n` with `Z_n` i.i.d. from `F₁`, the distribution of `X₁` (mean `μ`, variance `σ²`)
- `F_n(x) = F₁(x / α^(n−1))`, `f_n(x) = α^−(n−1) f₁(x / α^(n−1))`, hazard `r_n(x) = α^−(n−1) r₁(x / α^(n−1))`
- `E[X_n] = α^(n−1) μ`, `Var[X_n] = α^(2(n−1)) σ²`
- if `X₁` is exponential, gamma, Weibull or log-normal, every `X_n` stays in that family with the same shape; only the scale changes. Exponential `X₁` gives the geometric (Moranda) model, rate `λ_n = λ₁ / α^(n−1)`.
- expected failures `m(t) = Σ_{n≥1} G_n(t)`, `G_n` = cdf of `X₁+…+X_n` (compute numerically or by simulation); remaining over a lifecycle `T_c`: `m(T_c) − m(t)`
- quick fit: regress `ln x_n` on `n − 1`; slope ≈ `ln α`. After `n` failures, expected next gap `α^n μ` and `R(x) = 1 − F₁(x / α^n)`.

## 4. Practical use

1. **Check for growth first** (Laplace test). With `k` equal intervals and `n_i` failures in interval `i`: `u = [Σ(i−1)n_i − ((k−1)/2)Σn_i] / √(((k²−1)/12)·Σn_i)`. With failure times in `(0, T]`: `u = (ΣS_i/n − T/2) / (T·√(1/(12n)))`. `u < −2` means significant growth, `u ≈ 0` stable, `u > 2` getting worse. Without growth, a growth model's output is meaningless; find out why (new code landing, fixes breaking things, shifting test mix).
2. **Fit 2–3 candidates.** GO as baseline; PNZ or an S-shaped model if the curve starts slow; JM, SW or quasi-renewal if you have inter-failure times. Prefer MLE. `scipy.optimize.curve_fit` on cumulative counts gives a fine starting point but too-narrow error bars, because cumulative points are correlated.
3. **Pick and check.** Compare AIC `= 2k − 2 ln L`; better, refit on the first ~70% of the data and see which model predicts the rest. The `a`/`N` estimate should settle as data arrive; if it keeps climbing, the model under-predicts.
4. **Estimate** remaining faults, current intensity, `R(x|T)` and extra test time to target. Report a range (bootstrap or profile likelihood), not one number.
5. **Decide.** Ready when the trend shows growth, the current intensity's upper bound is at or below the target from section 1, and no high-severity failures are open. If not, `t* − T` is the extra test time at the current find-and-fix pace: a planning estimate, not a promise.

Test intensity predicts field intensity only if tests followed the operational profile. If one test hour exercises about `C` hours of field usage, `λ_field ≈ λ_test / C`.

Goel-Okumoto fit to grouped counts (needs numpy and scipy):

```python
import numpy as np
from scipy.optimize import curve_fit, minimize

# t: end of each test interval (execution hours); y: cumulative failures by t
t = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], float)
y = np.array([8, 15, 20, 25, 28, 31, 33, 35, 36, 37], float)
dy = np.diff(y, prepend=0)                     # failures per interval

k = len(dy)                                    # Laplace trend test (equal intervals)
u = (np.sum(np.arange(k) * dy) - (k - 1) / 2 * dy.sum()) / np.sqrt((k**2 - 1) / 12 * dy.sum())
assert u < -2, f"no significant reliability growth (u={u:.2f}); a growth model won't fit"

def m(t, a, b):                                # Goel-Okumoto mean value function
    return a * (1 - np.exp(-b * t))

# 1) least squares: good start point; its error bars are too narrow (cumulative data are autocorrelated)
(a, b), _ = curve_fit(m, t, y, p0=[1.5 * y[-1], 1 / t[-1]], bounds=(0, np.inf))

# 2) Poisson MLE on per-interval counts (preferred estimate)
def nll(p):
    dm = np.diff(m(t, *np.exp(p)), prepend=0)  # log-params keep a, b > 0
    return np.sum(dm - dy * np.log(dm))
a, b = np.exp(minimize(nll, np.log([a, b]), method="Nelder-Mead").x)

T, target = t[-1], 0.05                        # target: 0.05 failures per hour
remaining = a - m(T, a, b)                     # expected latent faults
intensity = a * b * np.exp(-b * T)             # current failure intensity
extra = max(0.0, np.log(a * b / target) / b - T)       # more test hours to hit target
R = lambda x: np.exp(-(m(T + x, a, b) - m(T, a, b)))   # P(no failure in next x hours)
print(f"u={u:.2f} a={a:.1f} b={b:.4f} remaining={remaining:.1f} "
      f"intensity={intensity:.3f}/h extra={extra:.0f}h R(10h)={R(10):.2f}")
# -> u=-3.69 a=41.2 b=0.0229 remaining=4.2 intensity=0.095/h extra=28h R(10h)=0.43
```

Limits: with fewer than ~20 failures the intervals are wide. The models assume a stable codebase, independent failures and a fixed usage profile. Treat the output as one input to the release decision, next to test results, open-bug review and staged-rollout data ([testing.md](testing.md)), not as proof of reliability.

## 5. Source notes

Where the reference pages differ from the standard literature (Lyu, *Handbook of Software Reliability Engineering*; Pham, *System Software Reliability*), this file uses the standard form:
- The reliability-testing page gives only `MTBF = MTTF + MTTR`; the availability, ROCOF and POFOD formulas here are the standard ones.
- The JM page calls the model an NHPP. JM is a finite-fault (binomial-type) model with exponential times between failures; GO is its NHPP counterpart.
- The SW page's pdf drops the minus sign and `φ` from the exponent; the correct exponent is `−φ(N−i+1)t_i²/2`, which matches the page's own reliability and likelihood.
- The PNZ page prints `(1 − α/β)` in `m(t)`. Solving `dm/dt = b(t)(a(t) − m(t))` with `m(0) = 0` gives `(1 − α/b)`, as in Pham-Nordmann-Zhang (1999).
- The quasi-renewal page writes `X_i = αX_(i−1)` with independent `X_i`. The standard definition is `X_n = α^(n−1)Z_n` with i.i.d. `Z_n` (equality in distribution).
- The GO page describes development "phases" and calls the model linear; neither applies to this growth model. Its formulas and MLE equations match the literature.
