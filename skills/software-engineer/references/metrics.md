# Software measurement and metrics

Use this when estimating size/effort, judging code complexity or quality, deciding what to refactor or test first, or when the user asks for metrics.

## Contents
1. Kinds of metrics and how to use them
2. Code metrics: LOC, cyclomatic complexity, Halstead
3. Size estimation: function points
4. Process and people metrics
5. Tools

## 1. Kinds of metrics and how to use them

- **Product** — the software itself: size, complexity, coverage, defect density, maintainability.
- **Process** — how the work gets done: lead time, cycle time, throughput, WIP, defect injection/escape rate, effort and schedule variance.
- **Project** — progress and planning: estimate accuracy, cost variance, staffing.
- **Direct** measures are counted (LOC, defects found); **indirect** ones are derived (defect density = defects / KLOC, maintainability index).

Good metrics are numeric, clearly defined, cheap and repeatable to collect, and as language-independent as possible. Use the loop: decide the question → pick the metric that answers it → collect → interpret in context → act → re-measure.

Pitfalls:
- A metric that becomes a target stops measuring anything (Goodhart). Never optimize for LOC or coverage numbers by themselves.
- Metrics describe the product/process, not a person's worth. Don't rank individuals by LOC or commit counts.
- Collecting data nobody acts on is waste. Wrong data → wrong decisions.

## 2. Code metrics

### Lines of code (LOC / KLOC)
- Counts non-blank, non-comment lines; excludes third-party code.
- Derived: defects/KLOC, cost/KLOC, KLOC/person-month.
- Cheap and easy to explain, but language- and style-dependent, blind to complexity, and rewards verbosity. Compare only within the same language and coding standards. Fewer lines for the same behavior is usually better.

### Cyclomatic complexity (McCabe)
- Number of linearly independent paths through a function.
- **M = decision points + 1** (each `if`, `elif`, loop, `case`, `catch`, `&&`/`||`, ternary adds 1). Graph form: M = E − N + 2P (edges, nodes, connected components; P = 1 for one function).
- **M is the minimum number of tests for basis-path coverage** of that function — a useful floor when writing white-box tests.
- Common interpretation: 1–10 simple; 11–20 moderate, consider splitting; 21–50 complex, high risk; >50 effectively untestable.
- Use it to find refactor and test hotspots: high complexity × high churn × low coverage = top risk.
- Limits: ignores data complexity; deep nesting reads worse than its number suggests (cognitive complexity covers that better).

### Halstead metrics
From operators/operands in the code: n1, n2 = distinct operators/operands; N1, N2 = total occurrences.
- Vocabulary n = n1 + n2 · Length N = N1 + N2 · Estimated length N^ = n1·log2 n1 + n2·log2 n2
- Volume V = N·log2 n · Difficulty D = (n1/2)·(N2/n2) · Effort E = D·V · Time T ≈ E/18 seconds · Estimated bugs B ≈ V/3000
- Needs complete code, weak as a predictor; mainly useful as an input to the maintainability index and for comparing versions of the same code.

## 3. Size estimation: function points (FP)

Language-independent size from requirements, before code exists — useful for effort/cost estimates of medium–large work.

1. Count the five components:

| Component | Meaning | Low | Avg | High |
|---|---|---|---|---|
| EI — external input | data/control entering (forms, API writes) | 3 | 4 | 6 |
| EO — external output | derived data leaving (reports, computed responses) | 4 | 5 | 7 |
| EQ — external inquiry | simple retrieval without derivation | 3 | 4 | 6 |
| ILF — internal logical file | data group the app maintains (a table/aggregate) | 7 | 10 | 15 |
| EIF — external interface file | data group read from another system | 5 | 7 | 10 |

2. UFP = Σ(count × weight).
3. Rate 14 general system characteristics 0–5 (data communications, distributed processing, performance, heavily used configuration, transaction rate, online data entry, end-user efficiency, online update, complex processing, reusability, installation ease, operational ease, multiple sites, facilitate change); sum = Σfi (0–70).
4. CAF = 0.65 + 0.01 × Σfi (0.65–1.35). **FP = UFP × CAF.**
5. Convert to effort with the team's own historical productivity (hours/FP) — that's the only conversion worth trusting.

Judgment-heavy and slow; for small tasks, a story-point or "split into ≤1-day tasks and sum" estimate is enough. When uncertain, give a range and the main risk, and use a spike to narrow it.

## 4. Process and people metrics

- **Delivery (DORA)**: deployment frequency, lead time for changes, change failure rate, time to restore service.
- **Flow**: lead time, cycle time, throughput, WIP, process efficiency (value-added time / total time).
- **Quality**: defect density, escaped defects, defect injection rate by phase, mean time to detect/repair.
- **People/team**: satisfaction (eNPS), attrition, collaboration — use only at team level, for support and early warning, never to rank individuals.

## 5. Tools

| Language | Complexity / Halstead / MI | LOC |
|---|---|---|
| Python | `radon cc -s`, `radon hal`, `radon mi`; ruff `C901` rule | `cloc`, `tokei` |
| JS/TS | ESLint `complexity` rule, `eslint-plugin-sonarjs` (cognitive) | `cloc`, `tokei` |
| Go | `gocyclo`, `gocognit` | `cloc`, `tokei` |
| Multi-language | `lizard` (CCN, LOC per function), SonarQube | `cloc`, `tokei`, `scc` |

Use what the project already has configured before installing anything.
