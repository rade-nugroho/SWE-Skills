# Debugging and maintenance

Use this when fixing a bug, changing existing or legacy code, or estimating what keeping a system alive will cost. It expands SKILL.md's rules: reproduce first (step 2), fix the root cause once in shared code (step 5), leave a regression test (step 6).

## Contents

1. [Debugging process](#1-debugging-process)
2. [Debugging strategies](#2-debugging-strategies)
3. [Agent tactics](#3-agent-tactics)
4. [Common bug classes](#4-common-bug-classes)
5. [Types of maintenance](#5-types-of-maintenance)
6. [Maintenance process](#6-maintenance-process)
7. [Legacy code](#7-legacy-code)
8. [Cost and effort of maintenance](#8-cost-and-effort-of-maintenance)

## 1. Debugging process

| Step | Do | Done when |
|---|---|---|
| 1. Reproduce | Run the failing command or write a failing test. Pin the exact input, versions, env vars, data, random seed. | It fails on demand. If it doesn't, say so instead of guessing at a fix. |
| 2. Isolate / localize | Shrink the input and the code path until little is left: smaller data, fewer modules, earlier commit. | You can point at a function, line range, or commit. |
| 3. Identify root cause | Explain *why* it fails, not just *where*. Keep asking "why" until you reach the code, data, or config decision that is wrong. | Your explanation predicts the failure, and predicts when it does *not* happen. |
| 4. Fix | Smallest change at the cause, once, in the shared code. Grep every caller of what you touch. | The fix follows from the explanation; you are not hoping. |
| 5. Verify | Regression test fails before the fix and passes after. Run the original repro, then the surrounding unit and integration suites. | You saw it pass. Nothing else broke. |
| 6. Prevent recurrence | Keep the regression test. Search for the same pattern elsewhere. Add a type, assert, or validation at the boundary that let bad data in. Record cause and fix in the commit/PR message. | The same class of bug would now be caught early. |

A symptom patch (catch-and-ignore, a special case for the one bad input, a retry or sleep around a race) hides the bug and makes the next one harder to find.

## 2. Debugging strategies

| Strategy | How | Use when | Watch out |
|---|---|---|---|
| Brute force (logging / printing) | Dump state widely and read it. | Small program, no other lead, or production where logs are all you have. | Slow and noisy. Use it to find a lead, then switch strategy. |
| Backtracking | Start at the failure (stack frame, wrong output) and walk backward through the code and data that produced it. | The failure site is known and the path to it is short. | The number of paths grows fast in large code; combine with slicing. |
| Forward tracing | Step from a known-good input with breakpoints or logs until the first wrong value appears. | You can run it locally under a debugger. | Stepping through loops is tedious; use conditional breakpoints. |
| Cause elimination / binary search | List candidate causes and rule them out; halve the search space (input, config, code path, commit range). `git bisect` automates it over history. | Regressions ("worked last week"), large inputs, many suspect changes. | Needs a reliable pass/fail check; flaky repros mislead bisection. |
| Program slicing | Keep only the statements that can affect the bad variable at the failure point (a backward slice); ignore the rest. | A wrong value in long or tangled code. | Done by hand it is approximate; follow aliases and globals too. |
| Hypothesis-driven | Observe → form one hypothesis → predict what an experiment will show → run it → keep or discard. | The default for any non-trivial or intermittent bug. | Write down what you ruled out so you don't retest it. |
| Static / dynamic tools | Type checker, linter, sanitizers (address, thread, UB), race detector, profiler, memory checker. | The bug class matches a tool: memory, races, types, leaks, slowness. | Tools find candidates; you still confirm the cause. |

Bisecting a regression (exit 0 = good, 125 = skip, other 1–127 = bad):

```sh
git bisect start
git bisect bad                # current commit fails
git bisect good <known-good-sha>
git bisect run ./repro.sh     # or: git bisect run pytest -x tests/test_cart.py
git bisect reset
```

## 3. Agent tactics

- **Read the whole error.** The full message and stack trace, including the innermost "caused by". The first frame in project code is usually more useful than the top line.
- **Make a minimal repro.** The smallest input or test that still fails. It becomes the regression test.
- **Check what changed.** `git log -p` on the suspect files, `git diff` against the last good state, lockfile and dependency bumps, config and env changes, data migrations.
- **Add targeted logs, then remove them.** Log inputs and outputs at boundaries with a unique prefix (e.g. `DBG-1234`), and grep for it before finishing.
- **One hypothesis, one change at a time.** Change one variable per experiment so the result means something.
- **Don't shotgun.** Editing several things at once and keeping whatever turns green leaves changes nobody can explain. Revert experiments that didn't help.
- **Step back after repeated misses.** If two or three well-reasoned hypotheses fail, your model of the system is wrong: re-read the code path and the assumptions, not just the next suspect line.
- **Can't reproduce?** Say so. Offer logging or an assertion that would capture the next occurrence rather than shipping an unverified fix.

## 4. Common bug classes

Check these first when the cause isn't obvious.

| Class | Typical symptom | Check |
|---|---|---|
| Off-by-one / boundaries | First or last item missing or duplicated | `<` vs `<=`, inclusive/exclusive ranges, empty and single-item inputs, pagination edges |
| Null / None / undefined | Null reference, `AttributeError`, "cannot read properties of undefined" | Optional returns, missing keys, empty query results, `0` or `""` treated as missing |
| Mutation / aliasing | A value changes somewhere unrelated | Shared mutable defaults (`def f(x=[])`), shallow copies, returning internal lists, objects shared between requests or tests |
| Async / race | Intermittent; passes alone, fails in the suite or under load | Missing `await`, check-then-act, shared state without locks, test order dependence, unhandled promise rejections |
| Time / timezone | Off by hours, wrong on DST days or at midnight/month end | Naive vs aware datetimes, store UTC, the test machine's TZ, clock injected vs `now()` |
| Float / decimal rounding | Totals off by a cent, `0.1 + 0.2 != 0.3` | Money as decimal or integer minor units, explicit rounding mode, compare floats with a tolerance |
| Encoding | Garbled text, crash on non-ASCII | Bytes vs text, explicit UTF-8 on every read/write, Unicode normalization, BOMs |
| Config / env drift | Works locally, fails in CI or prod | Env vars, runtime and dependency versions, lockfile, feature flags, locale, path case sensitivity |
| Caching / staleness | Old value after an update; a restart "fixes" it | Invalidation on write, TTLs, memo keys missing a parameter, build/CDN/browser caches |
| Swallowed errors | Silent wrong result, no log | Empty `catch`/`except`, ignored return codes, fire-and-forget tasks |

## 5. Types of maintenance

Maintenance is any change after delivery. Name the type, because it changes what "done" means.

| Type | Trigger | Examples | Done means |
|---|---|---|---|
| Corrective | A defect is found in use | Crash on empty cart; tax rounded wrong | Repro test fails before and passes after; root cause fixed; no other behavior changed |
| Adaptive | The environment changes: OS, runtime, dependency, external API, regulation | Runtime upgrade, replacing a deprecated SDK call, new data-retention law | Same behavior in the new environment; versions pinned; any dropped support stated |
| Perfective | Users want new or better behavior, including speed | CSV export, faster search, clearer error messages | Acceptance criteria met and tested; docs and changelog updated |
| Preventive | Risk of future failure or rising cost | Refactor a god class, add tests to an untested module, remove dead code, upgrade before end-of-life | Behavior unchanged (existing and characterization tests green); measurable gain such as lower complexity or more coverage |

ISO/IEC 14764 also groups them as reactive (corrective, adaptive) and proactive (perfective, preventive). Keep types apart in a diff: refactor in one commit, fix or feature in the next, so each can be reviewed and reverted on its own.

## 6. Maintenance process

1. **Change request** — what, why, which type, priority. For corrective work, reproduce it first.
2. **Impact analysis** — find everything the change reaches: callers, public APIs, schema and stored data, config, other services, docs. This sets the risk, the test plan, and whether a migration or flag is needed.
3. **Implement** — smallest complete change (SKILL.md section 5); test-first for fixes.
4. **Regression test** — new tests plus the full existing suite; for adaptive work, run in every environment you still support.
5. **Release** — changelog entry, version bump that signals the change (patch for a fix, minor for a compatible feature, major for a breaking change), rollback plan, and a look at logs and metrics afterward.

**Keep docs in sync** in the same change: README and usage, API docs/specs, `.env.example` and config samples, comments that describe the old behavior, runbooks. Stale docs raise the cost of every later change.

## 7. Legacy code

Treat "legacy" as "code without tests": you can't change it safely because nothing tells you what it did before.

- **Characterization tests first.** Before editing untested code, write tests that pin its *current* behavior: run it on representative inputs and assert the outputs it actually produces, even odd ones. If you find a bug this way, note it and fix it as a separate step.
- **Find a seam.** A place to substitute a dependency without editing much: a parameter, constructor argument, or module-level function. Add the smallest seam you need to get the code under test.
- **Small safe refactors.** Rename, extract function, inline, move, one at a time, with tests run between steps. Prefer the IDE's or language tooling's automated refactorings.
- **Sprout or wrap.** Put new logic in a new, tested function or class and call it from the old code, instead of editing deep inside a large untested function.
- **Strangler fig** for replacing a system: put a facade or proxy in front, move one feature at a time to the new implementation, route traffic over, and delete the old path once nothing uses it. It avoids the big-bang rewrite, which tends to stall and to lose behavior nobody wrote down.
- **Stay in scope.** Improve what the task touches; leave unrelated cleanup for its own change.

## 8. Cost and effort of maintenance

Maintenance usually costs more than development: it is commonly put at 60–80% of lifecycle cost, and a system is often maintained for many more years than it took to build. In Lientz and Swanson's classic survey, enhancements were about half of maintenance effort and bug fixing about a fifth.

### Cost drivers

| Group | Driver | Raises cost when |
|---|---|---|
| Listed by the source | Complexity and size | The system is large or tangled |
| | Rate of change | Requirements or environment change often |
| | Skilled staff | Experienced maintainers are scarce |
| | Tools | No automated tests, version control, or configuration management |
| | Maintenance plan | Work is ad hoc rather than planned |
| Non-technical (standard textbooks) | Application domain | The domain itself keeps changing |
| | Team stability | Original developers leave; newcomers must relearn the code |
| | Program age | Years of patches have eroded the structure |
| | External environment | It depends on platforms, regulations, or APIs that change |
| | Platform stability | Hardware or OS changes force adaptive work |
| Technical (standard textbooks) | Module independence | High coupling: one change ripples through many modules |
| | Language and style | Code is hard to read or uses obscure constructs |
| | Validation and testing | Low coverage makes every change risky |
| | Documentation | Missing or out of date |
| | Configuration management | Unclear which version runs where |

### Effort models

**Belady–Lehman** (the formula the source gives, unattributed there; standard texts such as Pressman credit Belady and Lehman):

```
M = P + K · e^(C − D)
```

M = total maintenance effort; P = productive effort (analysis, design, coding, testing); K = an empirical constant calibrated from past projects; C = complexity caused by poor design and documentation; D = the maintainers' familiarity with the software. The point: effort grows exponentially once complexity outruns familiarity, so tangled code plus staff turnover is the expensive combination.

**Boehm / COCOMO annual maintenance effort** (not on the source page; from Boehm, *Software Engineering Economics*, 1981):

```
AME = ACT × SDE × EAF
```

- **ACT** (annual change traffic) = fraction of the code changed in a year = (KLOC added + KLOC modified) / total KLOC. Some textbooks write "added + deleted"; the idea is the same.
- **SDE** = original development effort in person-months. Boehm's base form is just ACT × SDE.
- **EAF** = effort adjustment factor: the product of the COCOMO cost-driver multipliers (product complexity, required reliability, team capability, tooling, and so on).
- Example: SDE = 600 PM, ACT = 0.15, EAF = 1.1 → 600 × 0.15 × 1.1 = 99 PM/year, about 8 full-time people.

Both are rough, order-of-magnitude tools. Calibrate K and EAF against your own history before trusting the numbers. For complexity and size metrics, see `metrics.md`.

### Practical takeaway

The models say the same thing as experience: you pay for code quality every year the system lives, not once.

- **Readable code** lowers C and raises D for every new maintainer. Much of maintenance time goes to understanding existing code, so clarity pays off every time someone reads it.
- **Tested code** keeps each change cheap to verify and makes refactoring safe, so the structure can improve instead of decaying.
- **Low coupling** keeps impact analysis small: a change touches fewer modules, so the effective change traffic and the regression risk stay low.
- **Current docs** preserve familiarity (D) through staff turnover.
- **Every shortcut** adds to C (technical debt) and is paid back with interest on every later change. When you take one, mark it so it can be found and repaid.
