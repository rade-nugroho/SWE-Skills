# Testing

## Contents

1. [Verification vs validation](#verification-vs-validation)
2. [Seven testing principles](#seven-testing-principles)
3. [Testing guidelines](#testing-guidelines)
4. [Levels](#levels)
5. [Test-first loop](#test-first-loop)
6. [Black-box techniques](#black-box-techniques-from-the-spec)
7. [White-box techniques](#white-box-techniques-from-the-code)
8. [Unit testing](#unit-testing)
9. [Integration strategies](#integration-strategies)
10. [UI and browser automation](#ui-and-browser-automation)
11. [Performance testing: load and stress](#performance-testing-load-and-stress)
12. [Good tests](#good-tests)
13. [Checklist before reporting](#checklist-before-reporting)

## Verification vs validation

- **Verification** — did we build it right? Code meets the spec: tests, type checks, review.
- **Validation** — did we build the right thing? The behavior matches what the user actually needs: run it the way a user would, check against the FRs.

Do both. Passing unit tests on the wrong behavior is still wrong.

## Seven testing principles

| Principle | What it means for an agent writing tests |
|---|---|
| Testing shows defects are present, not that they're absent | A green suite is evidence, not proof. Say what you tested and what you didn't. |
| Exhaustive testing is impossible | Choose cases by risk, using partitions and boundaries. Don't try to list every input. |
| Test early | Turn requirements into acceptance tests before you write code. Ambiguity found at that point costs least to fix. |
| Defects cluster | Test hardest around the code you changed and its historically buggy neighbors. `git log` on the file and past fix commits show you where. |
| Pesticide paradox | Rerunning the same tests stops finding new bugs. Vary inputs and add cases, and every escaped bug gets a new test. |
| Testing depends on context | Scale rigor to risk. Money, auth, and data-loss paths need more than a throwaway script. Match the project's conventions. |
| Absence-of-errors fallacy | Bug-free code that solves the wrong problem has still failed. Validate against the user's real need, not only the spec. |

## Testing guidelines

- [ ] Set pass/fail criteria before you write a test. Each case states its input, steps, and expected result.
- [ ] Cover the happy path, edge cases, and invalid input.
- [ ] Use realistic data plus nasty data: empty, huge, unicode, nulls, duplicates.
- [ ] Automate anything you'll run more than once. Keep manual exploratory testing for usability.
- [ ] Combine levels: unit for logic, integration for boundaries, system/acceptance for user flows.
- [ ] Write tests first where practical (TDD), which keeps refactors safe.
- [ ] Use the project's existing test framework and runner. Don't add a second one.
- [ ] Run tests on every change (locally and in CI), not just at the end.
- [ ] Check the result from the end user's point of view before calling it done.
- [ ] Record what you ran and what happened, so the next person can reproduce it.

## Levels

| Level | Scope | When |
|---|---|---|
| Unit | one function/class, dependencies faked | all new logic |
| Integration | several modules or a real dependency (DB, file, HTTP via test server) | changes crossing a boundary |
| System / end-to-end | the whole app through its real interface (CLI, HTTP, UI) | user-facing flows, release checks |
| Acceptance | against the requirements / user's stated goal | features — map each FR to at least one test |
| Smoke | app builds, starts, main path works | after a build or deploy, before deeper testing |
| Regression | re-runs existing suite; one new test per fixed bug | every change |

Non-functional testing (load, stress, security, compatibility) only when an NFR demands it.

## Test-first loop

Red → green → refactor: write a failing test for the next small behavior, write the simplest code that passes, then clean up with the suite green. Acceptance criteria (given/when/then) from the requirements are the first tests to write; unit tests for edge cases follow.

## Black-box techniques (from the spec)

These need no knowledge of the code, which makes them good at finding missing or misread requirements. They can't show which internal paths ran, so pair them with white-box checks on the code you changed.

- **Equivalence partitioning** — split inputs into classes that should behave the same; test one value per class (valid and invalid).
- **Boundary value analysis** — test at, just below, and just above each boundary (0, 1, max, max+1, empty, one element).
- **Decision tables / cause-effect** — list the conditions (causes) and the actions (effects). Each rule column becomes one test, and "don't care" entries collapse the combinations.
- **State transitions** — for lifecycles, test each valid transition and at least one invalid one.
- **Use-case / scenario** — derive tests from end-to-end user flows, including alternate and error flows.
- **Pairwise (all-pairs)** — when many parameters interact, cover every pair of values rather than the full cross product.
- **Error guessing** — from experience, target the usual failures: off-by-one, null/empty, zero/negative, duplicates, whitespace, very long strings, time zones/DST, leap days, float rounding on money, concurrent calls.

Example — discount percent valid range 0–100:
classes: <0 (invalid), 0–100 (valid), >100 (invalid) → boundaries: -1, 0, 1, 99, 100, 101.

Example decision table — free shipping if member or total ≥ 50, never for oversized items (4 tests instead of 8):

| | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| oversized | Y | N | N | N |
| member | – | Y | N | N |
| total ≥ 50 | – | – | Y | N |
| **free shipping** | no | yes | yes | no |

## White-box techniques (from the code)

Coverage criteria, weakest to strongest:

| Criterion | Requires | Note |
|---|---|---|
| Statement | every statement runs once | Misses the false side of an `if` that has no `else`. |
| Branch (decision) | every decision goes both true and false | The practical default for changed code. Implies statement coverage. |
| Condition | every atomic condition in a compound test goes both true and false | `a and b` with (T,F),(F,T) satisfies it but never takes the true branch, so pair it with branch coverage. |
| Multiple condition | every combination of atomic conditions | 2ⁿ cases. Keep it for small, critical predicates. |
| Path | every distinct path | Infeasible once loops are involved, so use basis paths instead. |

```python
def fee(amount, member):
    charge = 5
    if member:
        charge = 0
    return charge
```
`fee(10, True)` gives 100% statement coverage but never checks non-members. Branch coverage also needs `fee(10, False)`.

**Basis path testing.** Cyclomatic complexity V(G) = E − N + 2 on the control-flow graph, which equals the number of binary decisions + 1. V(G) is the number of independent paths. Write at least that many tests, each flipping one decision from a baseline path. A V(G) above about 10 suggests the function should be split.

```python
def classify(xs):            # decisions: for, if → V(G) = 3
    out = []
    for x in xs:
        out.append("neg" if x < 0 else "ok")
    return out
```
Basis paths: `[]` (loop skipped), `[1]` (else side), `[-1]` (if side).

**Loop testing.**
- Simple loop with max n: 0, 1, 2, a typical count, n−1, n, n+1 (if it can be forced).
- Nested loops: start with the innermost and hold the outer loops at their minimum. Run the simple-loop cases, then work outward.
- Concatenated loops: test each one as a simple loop if they're independent. If the second uses the first's result, treat them as nested.
- Unstructured loops (jumps in and out): refactor before you test.

**Data-flow testing.** Follow each variable from where it's defined (assigned) to where it's used, and cover each def-use pair along some path. It catches values used before they're defined, defined but never used, and overwritten before use. Example: if `discount` is assigned only inside an `if` and read after it, test the path where the `if` is false.

**Mutation testing.** Make small changes to the code (`<` → `<=`, delete a line). If the suite still passes, the tests are weak there. Use it if the project already has a tool (mutmut, Stryker, PIT).

Use a coverage tool to find untested branches in the diff. Chase those, not a coverage number.

## Unit testing

A good unit is small, has one job, and shows its behavior through inputs and outputs. Hard-to-test code usually hides dependencies: pass the clock, DB handle, or HTTP client in rather than reaching for globals.

**Isolation with test doubles.** Replace only what makes the test slow, flaky, or non-deterministic (network, DB, clock, randomness).

| Double | What it does | Use when |
|---|---|---|
| Dummy | Fills a parameter, never used | the signature needs an argument the test ignores |
| Stub | Returns canned answers | you need the dependency's output to drive the code (a rate lookup returns 1.2) |
| Fake | Working but simplified version (in-memory repo) | many tests need realistic behavior without the real system |
| Mock | Pre-programmed with expected calls; fails if they don't happen | the call itself is the outcome (email was sent once) |
| Spy | Real or stub object that records calls for later asserts | you want to observe a side effect without scripting it up front |

Prefer stubs and fakes (check state) over mocks (check interactions); mock only when the interaction is the requirement.

**Arrange / act / assert.** Build inputs and doubles, call the unit once, assert on the result or visible side effect. Clean up in fixtures so tests don't affect each other.

**What not to unit test:**
- Third-party or framework internals (test your use of them at the boundary), and trivial getters or pure wiring.
- Private methods directly; reach them through public behavior.
- Anything that only means something against a real DB, network, or UI: that is an integration test.

**Common mistakes**
- **Testing the mock:** the assertion only confirms what you scripted, so it passes whatever the code does. Assert on real output or state.
- **Over-mocking:** the test passes while production differs, and every refactor breaks it. Fake only slow or non-deterministic edges.
- **Asserting implementation details** (call order, private fields): behavior-preserving refactors fail the test. Assert what callers can see.
- **Order or shared-state dependence:** fails alone or only in the full run. Use fresh fixtures.

```python
def test_total_applies_member_discount():
    rates = StubRates({"EUR": 1.1})                      # arrange: stub the lookup
    cart = Cart(rates, items=[Item(price=100)], member=True)
    total = cart.total("EUR")                            # act
    assert total == 99.0                                 # assert: 100 * 0.9 * 1.1
```

Unit tests say nothing about wiring, performance, or the UI.

## Integration strategies

A **stub** stands in for a lower module the code calls and returns canned answers. A **driver** is test code that calls the module under test in place of its real caller.

| Strategy | How | Scaffolding | Use when | Watch out |
|---|---|---|---|---|
| Big-bang | wire everything together, then test | none | few, simple modules that are all ready | failures are hard to localize; integration happens late |
| Top-down | start at the entry point (UI/controller) and add lower layers one level at a time | stubs | you want the main workflows and architecture checked early | stubs can hide real behavior; DB/I/O bugs show up late |
| Bottom-up | start at the lowest layer (data access, core algorithms) and build upward | drivers | low-level parts are risky or ready first | no end-to-end flow until the top layer arrives |
| Sandwich / hybrid | top-down on the upper layers and bottom-up on the lower ones in parallel, meeting in the middle | both | large layered systems, several people | most scaffolding; the middle layer is tested last |
| Incremental (general) | add one module or connection at a time and rerun tests after each | as needed | the default | slower to start than big-bang |

Top-down, bottom-up, and sandwich are all forms of incremental integration. As an agent, connect one piece at a time and run the suite after each. When a test fails just after you add module X, look at X or its interface first.

List the integration points (module calls, DB, external APIs) and cover failures at each: timeouts, error responses, malformed payloads, boundaries. Give each test its own data. Testcontainers runs a throwaway DB or broker; WireMock-style tools simulate a flaky third-party HTTP service.

## UI and browser automation

**Tool choice.** Use what the project already has: look for `playwright.config.*`, `cypress.config.*`, Selenium/WebDriverIO dependencies, or existing e2e folders. If there's none, propose one to the user rather than adding it quietly.

| Tool | Notes |
|---|---|
| Selenium WebDriver | W3C WebDriver standard, many languages, all major browsers. Grid (hub + nodes) runs tests in parallel across browsers and machines. Selenium IDE record/replay is for prototypes only. |
| Playwright | JS/TS, Python, Java, .NET. Chromium, Firefox, WebKit. Built-in auto-waiting, isolated browser contexts, traces. |
| Cypress | JS/TS. Runs inside the browser, retries assertions automatically, good local debugging. |

**Page-object pattern.** Give each page or component a class that exposes user-level actions and hides the selectors. Tests then read like scenarios, and a markup change touches one file. Put assertions in tests, not in page objects.

```ts
class LoginPage {
  constructor(private page: Page) {}
  async login(email: string, pw: string) {
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByLabel('Password').fill(pw);
    await this.page.getByRole('button', { name: 'Sign in' }).click();
  }
}
```

**Stable selectors**, best first: role plus accessible name, label, or visible text → a dedicated `data-testid` → CSS on meaningful attributes. Avoid generated class names (`.css-1x2y3z`), positional paths (`div > div:nth-child(3)`), and layout XPath. They break on cosmetic changes.

**No sleeps; wait for conditions.** Use Playwright/Cypress auto-waiting and retrying assertions (`await expect(locator).toBeVisible()`). In Selenium, use explicit waits (`WebDriverWait` with expected conditions) and don't mix them with implicit waits. A fixed sleep is either too slow or too short.

**Avoid flakiness:**
- Each test creates its own state, seeded through the API or DB rather than UI clicks, and runs in a fresh browser context. Don't depend on test order.
- Stub third-party network calls and control the clock.
- When a test fails intermittently, find the race (an un-awaited request, an animation, shared data). Don't paper over it with retries.
- Run each new UI test several times before trusting it.
- Keep e2e tests few and focused on critical user journeys. Push logic checks down to unit tests.
- Run headless in CI and save screenshots/traces on failure.

## Performance testing: load and stress

Run these when an NFR demands them or a hot path changed. The types differ in how load is shaped:

| Type | Goal | Load shape | Finds |
|---|---|---|---|
| Load | meet the target at expected and peak traffic | ramp to the expected level and hold | slow endpoints, bottlenecks, whether the NFR is met |
| Stress | find the limit and how it fails | climb past capacity until it breaks | breaking point, failure mode, recovery behavior |
| Spike | survive a sudden surge | jump from low to very high, then drop | autoscaling lag, queue overflow, connection pool exhaustion |
| Soak / endurance | stay healthy over time | normal load for hours | memory and connection leaks, disk growth, slow degradation |
| Volume | cope with lots of data | normal traffic against a very large dataset | slow queries, missing indexes, storage limits |

**Plan one**
- **Target** from the NFR (see `requirements.md`): "p95 under 300 ms at 500 req/s, errors under 0.1%". No target means nothing to pass or fail.
- **Workload mix** like production: the real ratio of reads to writes and the main user flows (login, search, checkout), with think time and varied data, not one URL hammered.
- **Environment** close to production (sizing, config, data volume) and isolated from other work.
- **Ramp-up** gradually, hold a steady state long enough to measure, and discard the warm-up window.
- **Measure** latency percentiles (p50, p95, p99; averages hide the slow tail), throughput, error rate, and saturation (CPU, memory, DB connections, thread and queue depth).

**Read the results.** Plot latency and errors against load. Latency stays flat, then bends upward: that bend is the knee, and safe capacity sits just below it. Past it, throughput flattens or falls while latency and errors climb. Find the resource that saturates first, fix it, rerun, one change per run, and compare against a baseline.

**Tools.** Use what the project has (k6 scripts, `locustfile.py`, `.jmx`, Gatling folders).

k6 (JS scripts, CI thresholds), Locust (Python flows), JMeter (GUI plus CLI, many protocols), Gatling (code DSL, detailed reports), wrk (quick raw HTTP on one endpoint).

**Pitfalls**
- Generating load from one machine: the load generator becomes the bottleneck. Watch its CPU and network, and distribute if it saturates.
- Coordinated omission: a closed-loop tool that waits for each reply stops sending during a stall, hiding the slow requests. Use an open model (fixed arrival rate) or a tool that corrects for it.
- Caches cold or unrealistically warm: replaying a few keys makes everything a hit. Use realistic key spread and state which cache condition you tested.
- Hitting production dependencies (payments, email, shared DBs): stub or sandbox them, and never point a stress test at production without agreement.

## Good tests

- Named for the behavior: `test_reserve_fails_when_stock_insufficient`.
- Arrange / act / assert; one behavior per test.
- Deterministic: inject clock, randomness, and I/O; no sleeps, no real network.
- Follow the project's existing framework, fixtures, and file layout.
- A regression test must fail on the old code. If you can, confirm it by running it before the fix.

## Checklist before reporting

- [ ] Bug fixes have a regression test that failed before the fix
- [ ] New logic covers happy path, partitions and boundaries, invalid input, and error paths
- [ ] Every branch in the changed code is exercised, and loops run 0, 1, and many times
- [ ] Multi-condition rules have one decision-table case per rule
- [ ] Extra tests sit around the risky neighbors of the change (defect clustering)
- [ ] Each FR touched has at least one test, and behavior is checked against the user's real need
- [ ] Boundaries were integrated incrementally, and tested against a real dependency or a faithful fake
- [ ] Unit tests fake only slow or non-deterministic edges and assert behavior, not mocks or internals
- [ ] UI tests (if any) use the project's tool, stable selectors, and no sleeps, and passed on repeated runs
- [ ] Performance tests (if an NFR requires) state a target, use a realistic workload, report percentiles, and compare to a baseline
- [ ] Whole suite run, not only the new tests; results recorded
- [ ] Linter / type checker / build run if the project has them
- [ ] No test weakened or deleted to make things pass
- [ ] Report states what was not tested
