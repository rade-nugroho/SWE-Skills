# Quality and Process

Process exists to make quality repeatable. Apply only as much as the task's size calls for: a one-line fix still gets a clean commit and a self-review; a release gets a tag, a changelog and an audit; formal maturity models matter only when the organization or the user asks for them.

## Contents

1. Software quality attributes: a review checklist
2. Software configuration management (SCM)
3. Software quality assurance (SQA)
4. Monitoring and control of a multi-step task
5. Process maturity models: ISO 9000, CMM, Six Sigma

## 1. Software quality attributes

Quality is several properties, not one. Review each change against the attributes it plausibly affects; most changes touch two or three.

| Attribute | Review question for this change |
|---|---|
| Correctness | Does it do exactly what the requirement and acceptance criteria say, edge cases included? |
| Reliability | What happens on bad input, timeouts, partial failure? Does it fail visibly and recover, or corrupt state? |
| Efficiency | Any new N+1 query, unbounded list or loop, extra network round trip, or big allocation on a hot path? |
| Security | Input validated at trust boundaries? Authorization checked? Secrets out of code and logs? Injection-safe? |
| Maintainability | Could the next engineer read and change it easily? Does it follow the existing structure, naming and error style? |
| Testability | Can its behavior be tested without heroics (injectable clock and I/O, small functions)? |
| Usability | Are error messages, CLI flags, API shapes and UI clear to the intended user and consistent with the rest? Accessible? |
| Portability | Hard-coded paths, OS-specific calls, locale or timezone assumptions, a runtime newer than the project supports? |
| Compatibility | Does it break existing callers, API clients, stored data, config files, or services it talks to? |
| Reusability | Did it reuse existing helpers instead of duplicating them? Is any new shared piece actually needed by more than one caller? |

Classic grouping (McCall): **operation** (correctness, reliability, efficiency, integrity, usability), **revision** (maintainability, flexibility, testability), **transition** (portability, reusability, interoperability). ISO/IEC 25010 is the current standard model and treats security and compatibility as top-level characteristics. When asked for a quality assessment, cover all three groups.

Attributes trade off against each other (efficiency vs readability, flexibility vs simplicity). When you make a trade-off, name it in the report.

Separate **quality of design** (requirements and architecture match what users need) from **quality of conformance** (the code matches the design). Tests mostly check conformance; validation (see `testing.md`) checks design.

## 2. Software configuration management (SCM)

SCM keeps the system in a known state: you can say exactly what is in a build, how it got there, and rebuild it. Each classic SCM activity maps to everyday practice.

| SCM activity | Meaning | Agent practice |
|---|---|---|
| Identification | Decide which items are under control (configuration items) | Version source, tests, build scripts, config templates, schemas and migrations, lockfiles, IaC, docs. Leave out build outputs, dependency folders, caches, local env files, secrets. |
| Version control | Every change to a controlled item is recorded and recoverable | Focused commits with clear messages; branches for work in progress; no untracked manual edits on servers. |
| Baselines | A reviewed snapshot that further work builds on | `main` with green CI is the working baseline; release tags are formal baselines. Branch from the baseline, not from someone's half-done branch. |
| Change control | Changes are requested, assessed for impact, approved, then made | The issue or user request is the change request. Check impact (callers, data, config, other services) before editing. PR review is the approval. Don't widen scope silently. |
| Status accounting | Record and report what changed and where each item stands | Commit messages, PR descriptions, changelog, release notes; link commits to the issue. |
| Configuration audit | Confirm the change is complete, correct, and matches what was approved | Before reporting or releasing: diff matches the request, nothing unintended staged, tests green on the exact commit, tag points at what was tested. |

### Commits

- One logical change per commit. Mixing a refactor, a reformat and a fix hurts reviewers and `git bisect` alike.
- Message: short imperative summary (about 50 to 72 characters), blank line, then a body explaining *why* and any non-obvious consequence. Reference the issue ID (`Fixes #123`) when there is one. Match the repo's convention (for example Conventional Commits); check `git log` first.
- Where practical, each commit builds and passes tests, so history stays bisectable.
- Stage files explicitly and read `git diff --staged` before committing, rather than adding everything blindly.
- Commit, push, tag, or open a PR only when the user asked or the workflow clearly expects it. Don't rewrite shared history (force-push, amending pushed commits) unless asked.

### Branches

- Work on a short-lived branch off the current default branch, named per the repo's scheme. Keep it current by rebase or merge, whichever the project uses.
- Commit straight to the default branch only if that is how the repo works and the user wants it.

### Keep out of the repo

- **Secrets**: API keys, tokens, passwords, private keys, `.env` files with real values. Use environment variables or the project's secret manager, and commit a `.env.example` with placeholders. If a secret was committed, treat it as leaked and tell the user it needs rotating; scrubbing history does not undo the exposure.
- **Generated artifacts**: `dist/`, `build/`, `node_modules/`, `__pycache__/`, coverage output, compiled binaries, logs. Add them to `.gitignore`. Exception: projects that deliberately commit generated code (checked-in protobuf stubs, vendored deps); follow that convention and regenerate instead of hand-editing.
- Large binaries, personal editor settings, OS clutter (`.DS_Store`), unless the repo already tracks them on purpose.

### Releases and reproducible builds

- Tag releases (annotated, e.g. `v1.4.2`) on the exact commit that was tested. With semantic versioning: patch for fixes, minor for backward-compatible features, major for breaking changes.
- Commit lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`, `Cargo.lock`, `go.sum`) and install from them in CI (`npm ci`, `pnpm install --frozen-lockfile`, `uv sync --locked`, `cargo build --locked`).
- Don't regenerate or bulk-upgrade a lockfile as a side effect of unrelated work; dependency bumps are their own change.
- Match the toolchain version the project pins (`.nvmrc`, `.python-version`, `rust-toolchain.toml`, the `go` directive).
- Builds should depend only on versioned inputs: no manual steps, no unpinned `latest` images, no piping remote install scripts into a shell.

### Traceability

Request → issue → branch → commits → PR and review → tag → release notes. Anyone should be able to go from a line of code (`git blame`) to the reason it exists, and from a bug report to the commit that fixed it.

## 3. Software quality assurance (SQA)

Testing finds defects in the product. SQA works on the process that prevents them: planned standards, reviews, audits and defect tracking applied throughout the work, not only at the end.

| SQA activity | Practice |
|---|---|
| Quality planning | Before coding, know what "done" means: acceptance criteria and which checks must pass (tests, lint, types, build). |
| Requirements review | Check requirements for ambiguity, contradiction and testability before building; ask when the answer changes what you'd build. |
| Standards | Run the project's linter, formatter and type checker; follow its style guide and conventions. Don't introduce a competing style or disable rules to silence warnings. |
| Reviews | Self-review the full diff before reporting (checklist below). For risky changes, recommend human review and say what to look at. |
| Audits | Audit your own process: did you actually run every command you're about to report? Is each claim backed by output you saw? |
| Defect tracking | Note defects you find but don't fix, with repro steps, in the report or as a drafted issue. For each fixed bug: root cause, regression test, and a search for the same pattern elsewhere. |
| Metrics | When asked to assess quality, use measurable signals (see `metrics.md`): defect counts, complexity, coverage of changed code, CI failure rate. |

SQA lowers defect rates but can't guarantee zero, and it costs time. Scale it to the risk of the change.

### Self-review checklist (run on the full diff)

- [ ] Only what the task needs: no debug prints, commented-out code, unrelated reformatting, or leftover spike code
- [ ] Each changed behavior has a test, or an explicit manual check you performed
- [ ] Linter, formatter, type checker, build and full test suite run and passing, with output seen
- [ ] Errors handled; inputs validated at trust boundaries; no secrets or personal data in code, logs or fixtures
- [ ] Names and structure match the surrounding code; comments explain why
- [ ] Callers, config, docs, migrations and changelog updated where the change made them stale
- [ ] Backward compatibility considered for public APIs, stored data and config formats
- [ ] Quality attributes from section 1 that this change touches have been checked
- [ ] No generated files, secrets or local-only files staged

## 4. Monitoring and control of a multi-step task

Monitoring compares actual progress to the plan; control acts on the gap. On a multi-step task the agent is its own project manager.

**Plan.** Split the work into steps, each with a concrete done-condition ("endpoint returns 201 and its test passes", not "work on the API"). Put the riskiest unknown early, with a spike if needed. Write down known risks and assumptions.

**Track.** Keep the step list current: pending, in progress, done, blocked. Mark a step done only when its done-condition is verified. Keep one step in progress at a time.

**Measure variance.** Watch for drift between plan and reality:

| Signal | Likely meaning |
|---|---|
| A step needs far more attempts than expected | Wrong approach, or wrong mental model of the code |
| New steps keep appearing | Scope is bigger than estimated |
| A fix needs edits in places you didn't plan to touch | Hidden coupling; impact is wider than thought |
| Earlier assumptions or test results stop holding | The plan rests on a wrong premise |
| The same error returns after a "fix" | Treating symptoms; root cause not found |

**Control.** Choose a corrective action on purpose instead of pushing on:

- Small drift: adjust the step and continue.
- Approach failing (say, the third failed attempt at the same idea): stop, re-read the code and the error, try a different approach rather than looping.
- Scope or risk materially larger than what the user agreed to: re-plan, then tell the user what changed, the options, and your recommendation before going further.
- Blocked on something only the user can supply (a decision, access, credentials): say so plainly and finish what you can meanwhile.

Update the task list on every re-plan so it always reflects reality.

**Report status honestly.** Updates and the final report state:

- Done and verified, done but unverified, and not done, as separate categories. Partial work is reported as partial.
- What changed from the original plan, and why.
- Open risks, and what would retire each one.
- Bad news as soon as you know it: a blocker found at step 2 is reported then, not after step 8.

## 5. Process maturity models

These are organization-level frameworks. They rarely change how you write a function, but they matter when the organization is regulated or certified (medical devices, aerospace, automotive, finance, government contracts), when the user asks for process improvement or audit preparation, or when a recurring class of defects needs a structured fix. In practice they demand traceability and evidence: requirement → change → review → test → release, all recorded.

**ISO 9000 family.** Quality-management standards; ISO 9001 is the one organizations get certified against through third-party audit. It targets the process rather than the product: documented procedures, planning, independent review of key documents, testing against the specification, records, and continual improvement. It says what must be controlled, not how to engineer software, so certification alone doesn't guarantee good software. For an agent: follow the documented procedure and leave an audit trail (linked issues, review records, test evidence).

**SEI CMM and CMMI.** Five maturity levels describing how predictable an organization's process is:

1. **Initial**: ad hoc; success depends on individual effort.
2. **Repeatable**: basic project management; planning, tracking, requirements management, configuration management, SQA.
3. **Defined**: organization-wide standard processes tailored per project; peer reviews, training.
4. **Managed**: quantitative quality goals for product and process; decisions driven by measurement.
5. **Optimizing**: continuous improvement from measured feedback; defect prevention and managed adoption of new technology.

CMMI succeeded CMM, extends it beyond software, and renames some levels (2 is Managed, 4 is Quantitatively Managed). Level 2's practices are exactly sections 2 to 4 of this file.

**Six Sigma.** A statistical, data-driven method for cutting variation and defects; the name refers to a target of about 3.4 defects per million opportunities.

- **DMAIC** improves an existing process: Define, Measure, Analyze, Improve, Control.
- **DMADV** designs a new process or product when improving the old one won't reach the goal: Define, Measure, Analyze, Design, Verify.

### DMAIC applied to a recurring defect class

Use this when the same kind of bug keeps returning (timezone errors, unhandled nulls from an API, missing authorization checks on new endpoints).

| Phase | Do |
|---|---|
| Define | Name the defect class and the goal precisely: "unvalidated optional fields from the payments API cause 500s; target zero in new code". |
| Measure | Get a baseline count: issue-tracker labels, error monitoring, `git log --grep`, a code search for the risky pattern. |
| Analyze | Find the cause the instances share, not each symptom: missing boundary validation, an unsafe helper, a confusing API, a missing kind of test. |
| Improve | Fix existing instances and remove the cause structurally: a typed parser at the boundary, a safe helper, a lint or static-analysis rule, a test template. Verify with tests. |
| Control | Keep it fixed: regression tests, the rule enforced in CI, a review-checklist item, a metric or alert. Re-measure later to confirm the count fell. |
