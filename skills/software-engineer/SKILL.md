---
name: software-engineer
description: End-to-end software engineering workflow for any code task in any language or stack — understand the code and requirements, size the design work (none, low-level design, or high-level system design), make the smallest complete change, test it at the right level, verify it actually works, and report honestly. Use this whenever the user asks to implement a feature, fix a bug, refactor, add an endpoint or module, build a script or small app, write functional/non-functional requirements, or design a system or component (HLD, LLD, architecture diagram, class or sequence diagram, "design X like Twitter/URL shortener") — even if they never say "software engineer" or "workflow". Not for pure infrastructure provisioning, security audits, or non-code writing.
---

# Software Engineer

Work like a careful senior engineer: understand before touching anything, design only as much as the change needs, write the smallest change that fully solves the problem, prove it works, then say plainly what you did and what you did not check.

The single most common failure is **mis-sized effort** — writing a design doc for a one-line fix, or hacking a new service together with no design at all. So size the task first.

## 1. Size the task

| Size | Looks like | Do |
|------|-----------|-----|
| Tiny | typo, rename, config value, one-line fix | Implement → verify → report. No requirements or design write-up. |
| Small | bug fix, one function, a feature inside one existing module | Understand → implement → test → verify → report. Design is a sentence in your head, not a document. |
| Medium | feature spanning several modules, new class/interface set, new API endpoint group | Add a short requirements list and a **low-level design** (section 4) before coding. |
| Large | new service or app, "design X", scaling an existing system, multi-team work | Requirements + estimation + **high-level design**, then split into modules and run the small/medium loop per module (section 4). |

If the user asks only for a design ("design a URL shortener"), the design document is the deliverable — don't write production code unless asked. If they ask for code, keep design notes short and put them in your reply, not in a separate doc, unless they asked for one.

## 2. Understand

Before editing, learn the ground you're standing on — wrong assumptions here cost far more than a few reads.

- Read the project's instruction files first if they exist — `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, README. They usually hold the build/test/lint commands, conventions, and known pitfalls, and they override your defaults.
- Read the code the change touches **and its callers**. A fix that breaks a caller is not a fix.
- Learn the project's conventions: language/runtime version, framework, folder layout, error-handling style, naming, how tests are written. Your code should look like it was always there.
- Find how to build, test, and lint (package.json scripts, Makefile, pyproject/tox, CI config, README). You need this for step 6.
- **Bugs: reproduce first.** Run the failing command or write a failing test. If you can't reproduce it, say so rather than guessing at a fix. If the cause isn't obvious after a first look, switch to a systematic strategy (bisect, cause elimination, one hypothesis at a time) — see `references/debugging-and-maintenance.md`, which also covers working safely in legacy/untested code.
- Ambiguity: if the answer changes what you'd build and you can't infer it from the code or context, ask one focused question. Otherwise choose the sensible default and state the assumption in your report.

## 3. Requirements (medium and large)

Write two short lists. Details and examples: `references/requirements.md`.

- **Functional** — what the system does. Write each as a user story with acceptance criteria: *As a [user], I want [behavior] so that [value]* + "Given / when / then" bullets with observable results. The acceptance criteria are your test scenarios — they map straight to tests in step 6.
- **Non-functional** — how well, under what constraints. Each gets a number and a workload ("p95 reserve latency < 50 ms at 200 req/s"). Vague words like "fast", "scalable", "secure" are not requirements until they have a target.
- **Out of scope** — what you're deliberately not doing. This keeps the change small and the user informed.

Only include NFRs that actually matter for this task. A CLI script doesn't need an availability target. If the user asks for a formal spec/SRS, `references/requirements.md` has the outline and quality checklist.

## 4. Design

For medium and large work, write a short **plan** before editing: files to touch, order of work, risks, and the tests that will prove it. Share it in your reply (or in a `plan.md` if the project works that way). If implementation diverges from the plan, say so in the report — a stale plan misleads reviewers.

### Low-level design (medium)
How the code inside a component is shaped. Read `references/low-level-design.md` when doing this.
1. Identify entities and give each a single responsibility.
2. Define interfaces where behavior genuinely varies (not "for later").
3. Define relationships — prefer composition over inheritance.
4. Walk through the main flow and its error paths.
5. Draw a Mermaid class and/or sequence diagram when there are more than ~3 interacting classes; skip it otherwise.

Prefer extending the existing structure over inventing a new one. No pattern, abstraction, or config option that nothing currently needs.

### High-level design (large)
How components fit together. Read `references/system-design.md` for the full process, building blocks, trade-offs, diagram rules, and a design-doc template.
1. Requirements (section 3) → 2. Back-of-envelope estimation (traffic, storage, bandwidth) → 3. API surface → 4. Data model and storage choice → 5. Component diagram (Mermaid flowchart) → 6. Deep-dive the 1–2 hardest parts → 7. Bottlenecks, failure modes, trade-offs.

Every design choice should trace back to a requirement or estimate. "Add Kafka" without a reason is noise. `system-design.md` ends with an index of deep-dive files (architecture styles, scaling, caching, load balancing, databases, consistency, queues, networking, distributed systems, security); open only the ones the decision in front of you needs.

### Specialized references (any size)
- Task adds or changes a schema, picks a datastore, or moves data → read `references/database-design.md` (conceptual → logical → physical design, reversible migrations, safe backfills).
- Task calls the network/DB/third parties, runs long jobs, or handles money/orders → read `references/fault-tolerance.md` (timeouts, retries, idempotency, transactions, fallbacks).
- Task touches authentication, authorization, secrets, user input, file uploads, or personal data → read `references/security.md` and run its review checklist on your diff.
- Task adds a cache, queue, rate limit, event flow, or a call between services → read the matching deep dive (`caching.md`, `api-gateway-queues-rate-limits.md`, `event-driven.md`, `distributed-systems.md`, `networking.md`).
- Task changes CI config, a release, or a deployment → read `references/ci-cd.md`.
- Task touches a screen, form, dashboard, or CLI → read `references/ui-design.md` (layout and visual hierarchy, density limits, tables/buttons/filters, interaction and accessibility checklist).
- Task has reliability/availability targets or asks whether software is reliable enough to release → read `references/reliability.md` (MTTF/MTBF/availability, reliability testing, growth models).
- Task asks for an effort/size estimate, a code-quality assessment, or where to refactor/test first → read `references/metrics.md` (cyclomatic complexity, LOC, Halstead, function points, process metrics).
- Task involves commits/branches/releases, a quality review, or process questions (SCM, SQA, CMM, Six Sigma) → read `references/quality-and-process.md`.

### Large builds: modularize, then iterate in small increments
For large *implementation* work: elicit requirements → split them into modules with clear interfaces → for each module, run analyze → design → code → test → integrate → test the whole product end to end. Define the interfaces between modules before building them so each can be built and tested on its own. Deliver in small working increments (the thinnest end-to-end slice first), verifying each one, rather than one big-bang drop at the end. Modules that touch disjoint files can be built in parallel (subagents or separate git worktrees) if your environment supports it — start with two or three, and only as many as can still be reviewed.

### Spikes for uncertainty
If you don't know whether an approach, library, or API will work (or how big the work is), run a **spike** first: a small throwaway experiment — a 20-line script, a REPL check, reading the library source — that answers the one question. Then design with the answer. Delete the spike code; don't let it leak into the real change.

## 5. Implement

Take the first option that fully works:
1. Code that already exists in this repo (a helper, pattern, service) — use it the way the surrounding code does.
2. The standard library or platform feature.
3. A dependency already installed. Don't add a dependency for a few lines of code.
4. The minimum new code that works.

Work **test-first** where practical — always for bug fixes, usually for pure logic: write the failing test (red), make it pass with the simplest code (green), then refactor while the tests stay green. Refactor only the code you touched; a passing suite is what makes refactoring safe.

Then:
- Keep the diff focused on the task. Don't reformat or refactor unrelated code — it hides the real change from reviewers.
- Fix bugs at the root cause, once, in shared code — not by patching each symptom.
- Validate input at trust boundaries, handle errors that could lose data, never hard-code secrets.
- Comments explain *why*, not *what*.

## 6. Test and verify

Tests prove the change does what the requirements say. Details (levels, black/white-box techniques): `references/testing.md`.

- **Acceptance** → each acceptance criterion from step 3 has at least one test (or, for UI/manual checks, an explicit check you performed).
- **Bug fix** → a regression test that fails before the fix and passes after.
- **New logic** → unit tests for the happy path, boundary values, each equivalence class, and the error paths. A function's cyclomatic complexity (decision points + 1) is the minimum number of tests that exercise every independent path through it.
- **Crossing a boundary** (DB, network, file, another module) → an integration test, using the project's existing fixtures/mocks style.
- Use the project's test framework and conventions. Don't introduce a new one.

Then verify, for real, as a loop with a clear finish line:
- **Define the check** — one command (or short sequence) with an unambiguous pass condition, e.g. `pytest -q && ruff check . && mypy src` all exit 0. Run it, read the failure, fix, rerun until it passes.
- **Cap the loop.** If the same check still fails after ~3–5 genuinely different attempts, stop and report the blocker with the evidence (command, output, what you tried). Thrashing burns time and tends to produce worse code.
- Run the tests, plus type-checker/linter/build if the project has them. **Never claim something passes unless you ran it and saw it pass.**
- If feasible, run the actual program/endpoint once the way a user would. For UI changes, look at the result (browser/screenshot tools) and compare it to the mock or expected behavior, adjusting over a few rounds.
- For risky or large changes, get a review with fresh eyes — a reviewer subagent with clean context if available, otherwise flag it for the human. The author of the code shouldn't be its only approver.
- Re-read your full diff top to bottom before reporting.
- If a test fails, fix the cause. Never weaken or delete a test to make it pass unless the test itself is wrong — and then say so.

## 7. Ship-readiness (when it applies)

The work doesn't end when tests pass. For changes that will be deployed or used by others:
- **Docs** — update the README, usage docs, API docs, or changelog the change makes stale.
- **Rollout & rollback** — for risky changes (migrations, config, behavior users depend on), say how to roll back; prefer feature flags or expand/contract over big-bang switches.
- **Observability** — new failure modes should be visible: logs with context, metrics or alerts where the project already has them.
- **Stop at the production gate.** Don't push to protected branches, merge, deploy, or run migrations against shared environments unless the user explicitly asks. Hand off as a branch/PR or local changes; humans approve production.

Skip what doesn't apply; don't invent process for a script.

## 8. Report

End with a short report the user can act on:

```
**What changed** — files touched and the gist of each change.
**Why** — root cause (bugs) or the design decision (features), one or two lines.
**Verified** — exact commands run and their results (e.g. `pytest -q` → 14 passed).
**Not verified / assumptions / risks** — anything you couldn't run, assumptions you made, known limits.
**Follow-ups** — only real ones, if any.
```

For pure design requests, the report is the design doc itself plus a 2–3 line summary of the key decisions and open questions.

If the user corrected a mistake during the task that you'd likely repeat (a wrong test command, a convention you missed), suggest recording it in `CLAUDE.md`/`AGENTS.md` so the next session starts with it.

## Reference files

- `references/requirements.md` — functional vs non-functional, NFR categories, how to write measurable requirements, elicitation questions.
- `references/system-design.md` — HLD process, estimation cheatsheet, building blocks, trade-offs (CAP, consistency), HLD diagram rules, design-doc template, and the index of system-design deep dives:
  `architecture-styles.md`, `event-driven.md`, `scalability.md`, `availability-and-consistency.md`, `load-balancing.md`, `caching.md`, `api-gateway-queues-rate-limits.md`, `networking.md`, `distributed-systems.md`, `security.md`, `ci-cd.md` (all in `references/`).
- `references/low-level-design.md` — OOP, SOLID, when to use common patterns, HLD→LLD steps, UML via Mermaid.
- `references/testing.md` — test levels, test-first loop, black-box/white-box techniques, verification vs validation, test checklist.
- `references/ui-design.md` — layout, visual hierarchy, density limits, component rules (tables, buttons, filters), interaction/accessibility checklist, Palantir Workshop specifics.
- `references/database-design.md` — DB design lifecycle, choosing a database, normalization, query tuning, replication, sharding, Redis, migrations, backfills.
- `references/fault-tolerance.md` — recovery vs masking, code- and system-level fault-tolerance techniques, checklist.
- `references/metrics.md` — product/process/project metrics, LOC, cyclomatic complexity, Halstead, function points, tools.
- `references/reliability.md` — reliability metrics, reliability testing, reliability growth models (Jelinski-Moranda, Schick-Wolverton, Goel-Okumoto, PNZ, quasi-renewal).
- `references/debugging-and-maintenance.md` — debugging strategies, common bug classes, maintenance types, legacy-code tactics, maintenance cost.
- `references/quality-and-process.md` — quality attributes, configuration management, SQA, monitoring & control, ISO 9000 / CMM / Six Sigma.
