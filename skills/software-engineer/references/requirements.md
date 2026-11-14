# Requirements

Contents
1. Requirements engineering process (feasibility → elicitation → analysis → specification → validation → management)
2. Classification
3. Functional vs non-functional
4. Writing them well
5. NFR categories
6. Elicitation techniques
7. Elicitation challenges and how to handle them
8. Elicitation questions
9. SRS outline
10. SRS quality checklist
11. Checklist

## Requirements engineering process

The steps loop: a gap found while specifying or validating sends you back to elicitation. Scale each step to the task — for a small change it is a minute of thought, for a new system it is real work. Errors caught here are far cheaper than errors caught in code.

| Step | Purpose | Output | Agent-scale version |
|---|---|---|---|
| 1. Feasibility | Is it worth doing, and doable? | Go / no-go, key risks | Check stack, deps, access, time; raise blockers before coding |
| 2. Elicitation | Learn the domain and what stakeholders need | Raw needs, domain knowledge | Read request, code, tests, docs, issues; ask focused questions |
| 3. Analysis | Find conflicts, gaps, infeasible items; prioritize | Reconciled, ranked list | Resolve contradictions; rank must/should/could/won't |
| 4. Specification | Write requirements down precisely | SRS, spec, or stories + acceptance criteria | Short spec or acceptance list in the plan / PR |
| 5. Validation | Right requirements, well written? | Agreed requirements | Restate scope to the user; turn criteria into tests |
| 6. Management | Control change over the lifecycle | Versioned, traced requirements | Re-assess impact on each change; keep spec and tests in sync |

**Feasibility lenses** — technical (tech, skills, infrastructure, maintainability), operational (solves the problem; people will use and run it), economic (benefit justifies build + run cost), legal (regulation, licences, contracts, IP — often forgotten), schedule (deadline realistic for the scope).

**Analysis** — triage each requirement as *achievable*, *deferred* (keep it, record why), or *impossible* (drop it, tell the user). When prose is not enough, model it: data flow diagram (how data moves), ER diagram (entities and relations), function decomposition, data dictionary (one definition per term).

**Verification vs validation** — *verification* asks whether requirements are well formed: complete, consistent, unambiguous, testable (review, walkthrough, drafting test cases). *Validation* asks whether they are the right ones for the stakeholder (prototype, demo, scenario walk-through). Both continue through the project.

**Change control** — for each change: identify its source → assess impact on code, tests, schedule, other requirements → accept or reject → update spec, version, and trace links. Skipping this is how scope creep happens.

## Classification

| Type | Captures | Example |
|---|---|---|
| Functional | Behaviors: inputs → processing → outputs | Search products by name or category |
| Non-functional | Qualities and constraints on how it works | 99.9% uptime; encrypted in transit and at rest |
| Domain | Industry rules, terms, standards; come from the domain, not one user; can be functional or non-functional | HIPAA for patient records; GAAP for financial reports |

Other cuts (one requirement can sit in several):

| Type | Content |
|---|---|
| Business | Organizational goal and how success is measured (revenue, retention) |
| User | What users need, in plain language — the stakeholder's view |
| System | Detailed technical behavior, components, interfaces — the basis for design |
| Interface | Contracts with external systems: APIs, databases, services, file formats |
| Regulatory | Privacy, security, accessibility, compliance obligations |
| Design | Imposed architecture, data structures, algorithms — keep only real constraints (an SRS says *what*, not *how*) |

NFRs split into *execution* qualities (seen at runtime: performance, security, usability) and *evolution* qualities (in the structure: maintainability, testability, extensibility, scalability). Constraint kinds: interface, performance, operating, life-cycle, economic.

Classify to spot gaps (no NFRs at all? no regulatory check?) and to route each item to its proof: FR → test, NFR → benchmark or monitor, regulatory → review. Don't polish the taxonomy; a misfiled requirement is cheap, a missing one is not.

## Functional vs non-functional

- **Functional (FR)** — *what* the system does: features, behaviors, responses to inputs and events. Login, search, checkout, "send a notification when an order ships".
- **Non-functional (NFR)** — *how well* it does it and under what constraints: speed, scale, uptime, security, ease of change. NFRs drive architecture far more than FRs do.

Quick test: does the sentence describe a feature, or a quality/constraint on a feature?
- "Users can reset their password." → FR
- "Password reset completes within 5 s for 99% of requests." → NFR

## Writing them well

**FR:** actor + behavior + observable result. It should be checkable by comparing output to the expected behavior.
> A logged-in user can transfer money between their own accounts; both balances update atomically and the transfer appears in history.

For features, the user-story form makes the outcome testable by construction:

```
As a shopper, I want to reserve stock at checkout so that items don't sell out while I pay.
Acceptance criteria:
- Given 5 in stock, when I reserve 2, then available shows 3.
- Given 1 in stock, when I reserve 2, then the reservation is refused and stock is unchanged.
- Given a reservation older than 15 min, when stock is queried, then the reserved units are available again.
```

Each "given / when / then" line is a test scenario — write it as a test.

**NFR:** use the pattern *[metric] for [operation] is [target] under [workload/condition]*.
> Weak: "The site should be fast."
> Strong: "p95 balance lookup < 2 s at 500 concurrent users."

If you can't write a test or a monitor for it, it isn't a requirement yet.

## NFR categories (pick only the ones that matter)

| Category | Typical target |
|---|---|
| Performance | latency (p50/p95/p99), throughput (req/s) |
| Scalability | users / requests / data volume growth it must absorb |
| Availability | uptime % (99.9% ≈ 8.8 h downtime/yr; 99.99% ≈ 53 min/yr) |
| Reliability / durability | error rate, data-loss tolerance, recovery time (RTO) and point (RPO) |
| Security | authn/authz model, encryption at rest/in transit, data protection rules |
| Maintainability | testability, modularity, deploy frequency |
| Usability / accessibility | task completion, WCAG level |
| Portability / compatibility | platforms, browsers, runtimes supported |
| Cost | budget per month / per request |

## Elicitation techniques

Elicitation flow: identify stakeholders (who uses, builds, pays for, or is affected by it) → gather FRs and NFRs → prioritize → triage feasibility.

| Technique | How it works | Fits when |
|---|---|---|
| Existing artifacts | Read manuals, similar systems, standards, current code | Always; cheapest first source |
| Interview, structured | Prepared list of open questions | Domain shape known; need specific facts |
| Interview, open-ended | No agenda; context-free questions (who uses it? what does success look like?) | Problem still fuzzy |
| Brainstorming | Group produces many ideas; facilitator records all visibly, then ranks | Exploring options; new product |
| FAST | Joint customer–developer session: each lists objects around, produced by, and used by the system; merge, dedupe, sub-teams write mini-specs → draft spec | Builders and customers expect different things |
| QFD | Sort needs into *normal* (stated), *expected* (assumed, never said), *exciting* (delighters) | Prioritizing for satisfaction; surfacing implicit needs |
| Use cases | Actors (primary: owns the goal; secondary: the system relies on them) + interaction sequences covering every way the system is used | Behavior with several actors or flows |
| Prototype / mockup | Build something cheap and show it | User can react to something concrete but can't describe it |
| Surveys | Same questions to many people | Many users; measuring preferences |
| Observation / task analysis | Watch the real work | Documented process differs from actual; tacit rules |
| Workshops, role-play, Delphi | Group sessions; Delphi converges experts through anonymous rounds | Many stakeholders with differing views |

Agent equivalents: the interview is the chat; artifact analysis is reading code, tests, issues, and docs; the prototype is a stub, mock, or example output shown before the full build; use cases become the enumerated scenarios you test. QFD's *expected* bucket is what agents miss most: auth, input validation, error paths, concurrency, migrations, backward compatibility.

## Elicitation challenges and how to handle them

| Challenge | What to do |
|---|---|
| User unsure what they want | Propose a concrete default (smallest version that does the core job) and ask to confirm it |
| Ambiguous wording ("fast", "handle errors", "support X") | Ask one focused question with options, or state the interpretation you are taking |
| Conflicting requirements | Name the conflict and the trade-off; ask which wins rather than choosing silently |
| Unclear boundary / scope creep | Write in-scope and out-of-scope; confirm before large work; park extras as follow-ups |
| Requirements change mid-task | Restate the new scope; check impact on finished work; update spec and tests together |
| Domain or tacit rules | Look for existing rules in code, tests, fixtures; ask the user rather than invent them |
| Large system | Split into non-overlapping, independent parts with clear interfaces |
| Open TBDs | Keep few; list each as an open question with an owner, not a guess hidden in code |
| Inconsistent terms | One name per concept; reuse the codebase's names |
| Risk, cost, time | Flag risky or expensive items early, with a cheaper alternative |
| Lost traceability | Link each requirement to the test that proves it |

How to ask well:
- Do the homework first; ask only what the code, docs, and context can't answer.
- Batch questions in one message, each with options and your recommended default.
- Reversible, low-cost guess → proceed and state the assumption. Costly or irreversible (data loss, money, security, public API) → ask first.
- Write assumptions in the plan or PR so the user can correct them.
- Before big work, confirm scope back in one or two sentences; an example input/output or small table confirms faster than prose.

## Elicitation questions

Ask (or infer from context) only what changes the design:
- Who are the users and what are the 2–3 core things they do?
- Read-heavy or write-heavy? Rough ratio?
- Scale now and in 1–2 years (DAU, req/s, data size)?
- Latency expectations for the core path?
- What must never be lost or be wrong (money, orders)? → consistency/durability needs.
- Any hard constraints: existing stack, compliance, budget, deadline?
- What is explicitly out of scope?

## SRS outline

Use when the user asks for a spec, SRS, or requirements document. It works as the contract: what is in it gets built and tested; what is not is out of scope. Drop sections that don't apply — a single feature usually needs only 1, 3, 4, 5, 9, 12.

1. **Introduction** — purpose, intended readers, glossary
2. **Overview** — problem, target users, key features, platforms
3. **Goals and scope** — objectives; in scope; out of scope; later phases
4. **Functional requirements** — numbered (FR-1…), each with priority; use cases or user stories with acceptance criteria
5. **Non-functional requirements** — numbered (NFR-1…), each measurable
6. **Interfaces** — external systems, APIs, data formats
7. **Constraints and assumptions** — platform, stack, regulation, budget, dependencies
8. **Diagrams** — context, flows, data model, where they clarify
9. **Acceptance criteria** — what "done and releasable" means: test criteria plus user acceptance
10. **Risks** — each with a mitigation
11. **Plan** (only if asked) — deliverables, milestones, releases, tech stack
12. **Open questions** — each TBD with an owner

Writing it: plain language, one requirement per numbered item, bullets and tables over paragraphs, then review and revise until no item has two readings.

## SRS quality checklist

- [ ] **Correct** — each item is something the system truly must do, confirmed by the user, not inferred
- [ ] **Unambiguous** — one reasonable reading; terms defined in the glossary
- [ ] **Complete** — FRs and NFRs, behavior for valid and invalid input; TBDs resolved or listed with owners
- [ ] **Consistent** — no contradictions; one name per concept; same units and format throughout
- [ ] **Ranked** — each item has a priority and, where useful, stability (how likely to change)
- [ ] **Verifiable / testable** — a test, measurement, or inspection decides pass/fail; no "user-friendly"
- [ ] **Modifiable** — numbered, cross-referenced, no duplicates, so a change touches one place
- [ ] **Traceable** — back to its source (user, ticket, regulation), forward to design, code, tests
- [ ] **Design-independent** — states what, not how, unless the "how" is a real constraint
- [ ] **Understandable** — a domain expert who doesn't code can review it; minimal jargon
- [ ] **Right level of detail** — high-level for feasibility, precise for implementation; nothing irrelevant

Treat the SRS as living: revise it as the work teaches you more.

## Checklist

- [ ] Each FR is a specific behavior with a verifiable outcome
- [ ] Each NFR has a number and the workload/condition it applies to
- [ ] No unquantified "fast / scalable / secure" remain
- [ ] Conflicts noted (e.g. strong consistency vs latency, security vs usability) with the chosen trade-off
- [ ] Targets are realistic for the budget, infrastructure, and timeline
- [ ] Out-of-scope list written
