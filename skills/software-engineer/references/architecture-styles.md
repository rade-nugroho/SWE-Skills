# Architecture styles

Deep dive linked from `system-design.md`. Use it when choosing between a monolith, microservices, event-driven or serverless design, or when reviewing one.

## Contents
1. Styles at a glance
2. Decision guide
3. Microservices essentials and failure modes
4. Event-driven (short) and pub/sub
5. Serverless
6. Stateless vs stateful
7. Checklist: choosing and reviewing

## 1. Styles at a glance

| Style | Strengths | Costs | Pick when |
|---|---|---|---|
| Monolith | One codebase, one deploy; in-process calls (no network); simple local debugging and transactions | Everything scales and deploys together; coupling grows without discipline; one crash can take the whole process down | Small team, young product, requirements still moving |
| Modular monolith | All monolith benefits, plus enforced module boundaries and a clear path to extract services later | Needs real discipline (no cross-module table access, no reaching into internals) | Default for most new systems and for teams that have outgrown a tangled monolith |
| Microservices | Independent deploy and scaling per service; team autonomy; fault isolation; mixed tech possible | Network failures, latency, distributed data consistency, many pipelines, hard cross-service debugging and testing | Many teams blocked on one deploy, parts with very different scaling or availability needs |
| Event-driven | Loose coupling; absorbs spikes; easy to add consumers; async by default | Eventual consistency, duplicates, ordering, hard to trace an end-to-end flow | Fan-out of one fact to many reactors, buffering bursts, integrating systems that must not block each other |
| Serverless (FaaS + managed services) | No servers to run; scales to zero; pay per use; fast to ship | Cold starts, time/memory/payload limits, lock-in, awkward local testing, cost can flip at steady high load | Spiky or low-volume workloads, glue code, scheduled jobs, event handlers |

Styles combine: a modular monolith with a queue and one or two serverless functions is normal. Event-driven and serverless describe how parts communicate or run; they are not exclusive of the others.

```mermaid
flowchart LR
  A[Monolith] -->|enforce module boundaries| B[Modular monolith]
  B -->|extract only what has a concrete signal| C[Few services around a core]
  C -->|only if signals keep appearing| D[Microservices]
```

## 2. Decision guide

Default to a modular monolith. Splitting is a response to a measured or organizational problem, not a starting point. Why: every service boundary turns a function call into a network call that can fail, be slow, or be retried, and turns a transaction into a consistency problem.

Signals that justify extracting a service (need at least one concrete one, written in the design doc):

| Signal | Example evidence | Extract? |
|---|---|---|
| Different scaling profile | Image processing needs 20x the CPU of the rest; scaling the whole app wastes money | Yes, extract that component (often as a worker) |
| Team contention | Several teams blocked on one release train, frequent merge conflicts in the same modules | Yes, along team ownership lines |
| Different availability or compliance needs | Payments must stay up when the rest degrades, or must sit in an audited boundary | Yes |
| Different runtime or tech needs | ML inference in Python next to a JVM app | Yes |
| Slow build/test cycle only | Full test suite takes 40 minutes | No: fix with modular build, test selection, caching first |
| "It might scale someday" | No numbers | No |
| Resume or fashion | "Everyone uses microservices" | No |

Before extracting, check in code:
- The module already has a narrow public interface and no other module reads its tables. If not, fix that first: extraction is easy only after the seam exists.
- The data it owns can live in its own store. Joins across the boundary are a warning sign.
- Calls across the boundary are few and coarse, not dozens per request.
- The team can run it: deploy pipeline, dashboards, alerts, on-call (`ci-cd.md`, `reliability.md`).

Quick path for a new project: one repo, one deployable, top-level folders per business capability, an interface file per module, a lint or test rule that forbids imports of another module's internals. Sizing and scaling numbers: `scalability.md`.

## 3. Microservices essentials and failure modes

**Service boundaries.** Cut along business capabilities (billing, catalog, shipping), not technical layers ("the database service"). A good boundary: one team owns it, it changes for one reason, and most requests touch few services. Test: if two services always change and deploy together, they are one service.

**Database per service.** Each service owns its data; others go through its API or its events, never its tables. Shared databases couple deployments through the schema. Strict isolation is common practice rather than law, so if you share a database for now, document it as debt and keep schemas separate (`database-design.md`).

**Sync vs async communication**

| Use | When | Watch out |
|---|---|---|
| Sync (REST/gRPC) | Caller needs the answer now (price lookup, auth check) | Chained calls multiply latency and failure rates; set timeouts |
| Async (queue/events) | Caller does not need the result to continue; work can be retried; many reactors | Eventual consistency, duplicates, tracing |

Rule of thumb: queries sync, state-change notifications async. Keep sync call chains short (two hops is a smell worth reviewing, four is a bug).

**Supporting pieces**
- API gateway: one entry point for routing, authentication, rate limits, TLS. Keep business logic out of it. Run it replicated (`api-gateway-queues-rate-limits.md`).
- Service discovery: instances come and go, so callers resolve names through a registry or the platform's DNS (Kubernetes services, a service mesh), not hard-coded addresses (`networking.md`, `load-balancing.md`).
- Saga: a business transaction across services becomes a sequence of local transactions, each with a compensating action (refund, release stock). Two styles: orchestration (one coordinator tells each step what to do; easier to reason about) and choreography (services react to each other's events; looser but flow is hard to see). Make every step idempotent and persist saga state (`distributed-systems.md`).
- Circuit breaker, timeouts, retries with backoff and jitter, bulkheads, fallbacks: see `fault-tolerance.md`. Every remote call needs a timeout and a decision about what happens on failure.
- Observability: correlation/trace ID propagated on every call and event, structured logs, per-service RED metrics (rate, errors, duration), distributed tracing. Without these you cannot debug a request that crosses five services (`reliability.md`).
- Security: authenticate service-to-service calls, not only the edge (`security.md`).

**Typical failure modes**

| Failure mode | Symptom | Fix |
|---|---|---|
| Distributed monolith | Services must be deployed together, share a database, or break when one changes | Merge them back, or fix boundaries and contracts; version APIs |
| Chatty calls | One user request triggers dozens of inter-service calls; latency and cost grow | Coarser APIs, batch endpoints, local read models or caches, merge services |
| Cascading failure | One slow dependency exhausts threads everywhere | Timeouts, circuit breakers, bulkheads, load shedding |
| Data inconsistency | Orders exist without payments, stale copies | Sagas, outbox pattern, idempotent consumers, reconciliation jobs |
| Nano-services | Dozens of tiny services, one per function | Consolidate around capabilities |
| Missing ownership | Nobody on call for a service | One owning team per service, listed in a catalog |

## 4. Event-driven (short) and pub/sub

Event-driven architecture: producers publish events (facts that already happened) to a broker; consumers react without the producer knowing who they are. Gains: loose coupling, burst buffering, easy extension. Costs: eventual consistency, duplicate and out-of-order events, harder tracing. Event design, schemas, outbox, replay, and streaming vs queues live in `event-driven.md`.

**Pub/sub in practice**
- A publisher sends to a named topic; each subscription on that topic receives its own copy (fan-out), so one event can drive email, analytics and inventory independently.
- A subscription holds the consumer's position and delivery settings; consumers in the same subscription share the work.
- Delivery semantics: at-most-once (may lose), at-least-once (may duplicate; the usual default), exactly-once only in narrow, platform-specific forms. Design consumers to be idempotent (dedupe on event ID or make the write naturally repeatable). Ordering is usually guaranteed only within a partition or ordering key, so choose the key (for example the order ID) deliberately.
- Failed messages: bounded retries, then a dead-letter queue with an alert.

| | Pub/sub topic | Work queue |
|---|---|---|
| Who gets a message | Every subscription | One consumer among competing workers |
| Purpose | Notify many parties of a fact | Distribute tasks |
| Adding a new reader | Add a subscription; producer unchanged | Adds capacity, not a new reader |
| Typical use | `OrderPlaced` to billing, email, analytics | Resize image, send one email |

Many brokers do both (a topic with several subscriptions where each subscription behaves as a queue for its workers). Check what your broker calls each thing before assuming.

Before adding a broker, ask: does anyone need the result synchronously? Can a plain function call or a database table do the job? A queue is another system to run (`api-gateway-queues-rate-limits.md`).

## 5. Serverless

Two halves: FaaS (your code runs as functions triggered by HTTP, queue messages, schedules or storage events) and BaaS (managed auth, databases, storage and queues you call instead of running).

| Fits | Poor fit |
|---|---|
| Spiky or unpredictable traffic, scale to zero | Steady high load (a reserved server is often cheaper) |
| Event handlers, webhooks, scheduled jobs, glue between managed services | Long-running jobs beyond the platform time limit |
| Prototypes and small teams without ops capacity | Latency-critical paths that cannot absorb cold starts |
| Short stateless requests | Large in-memory state, persistent connections, specialized hardware |

Things to check in code and design:
- Cold starts: first request after idle (or after scale-out) is slower; heavy imports and large bundles make it worse. Keep functions small, initialize clients outside the handler, consider provisioned or warm capacity for latency-sensitive paths.
- Limits: execution time, memory, payload size, concurrency. Know the platform's numbers and design around them (chunk work, hand off to a queue).
- Stateless: no local disk or memory carried between invocations; state goes in managed stores. Handlers must be idempotent, since events are often delivered at least once.
- Concurrency can overwhelm a downstream database (each invocation opens a connection). Use a pool/proxy or cap concurrency.
- Cost shape: billed per invocation plus compute time and memory, so cost rises linearly with traffic and has no idle floor. Model it at expected peak before committing.
- Lock-in: triggers, permissions and managed services are provider-specific. Keep business logic in plain functions behind a thin handler so it can move.
- Local testing and debugging are harder: keep logic testable without the platform and add structured logs and tracing from the start.
- Security: least-privilege role per function, secrets from a secret manager, validate every event payload (`security.md`).

## 6. Stateless vs stateful

A stateless service keeps no per-client data between requests; any instance can serve any request. A stateful one remembers (sessions, carts, open connections, in-memory data). State never disappears: it moves to a client token, a shared store, or a database.

| Concern | Stateless service | Stateful service |
|---|---|---|
| Scaling | Add instances behind a load balancer | Needs replication or partitioning, rebalancing |
| Failover | Route to another instance | State may be lost or must be replicated first |
| Load balancing | Round robin or least connections | May need sticky routing |
| Operations | Cheap to restart, deploy, autoscale | Careful restarts, backups, data movement |

Where state can live:

| Location | Good for | Trade-off |
|---|---|---|
| Client token (JWT, signed cookie) | Identity and small claims | Larger requests; hard to revoke before expiry; never put secrets or large data in it |
| Shared cache (Redis) | Sessions, short-lived data | Extra dependency; eviction means lost session unless handled (`caching.md`) |
| Database | Durable state | Slower, load on the DB |
| Instance memory or disk | Local caches, in-flight work | Lost on restart; invisible to other instances |

Sticky sessions pin a client to one instance. They are a stopgap: load spreads unevenly, and an instance failure drops its users' sessions. Prefer externalizing session data so any instance works.

What to check in code when making a service scalable or reviewing one:
- Module-level mutable variables, singletons holding user data, in-process caches that must be consistent across instances.
- Sessions in memory, uploads written to local disk, local files used as queues.
- In-process schedulers and cron jobs that would run N times with N instances (use a leader lock or a single scheduler).
- WebSocket or other long-lived connections: stateful by nature; route by connection, and use a pub/sub backplane to reach users on other instances.
- Rate limit counters and locks kept per-instance instead of in a shared store.
- Any code that assumes the same instance handles the next request.

Stateful parts are fine when intended (databases, brokers, game servers). Keep them few, isolate them, and make everything else stateless. Scaling and failover patterns for stateful tiers: `scalability.md`, `availability-and-consistency.md`.

## 7. Checklist: choosing and reviewing

Choosing:
- [ ] Requirements and numbers (traffic, team size, availability target) are written down; the style traces back to them.
- [ ] Default considered first: modular monolith. Each departure names the concrete signal from section 2.
- [ ] Team can build and operate it (pipelines, on-call, dashboards), not only design it.
- [ ] Cost estimated at expected peak and at idle, including operational headcount.
- [ ] Reversibility: how hard to merge back or split further later?

Reviewing a modular monolith:
- [ ] Modules have explicit public interfaces; no cross-module table access or internal imports; a lint or test enforces it.
- [ ] Each module owns its data; cross-module queries go through the interface.

Reviewing microservices:
- [ ] Boundaries follow business capabilities; no pair of services that always deploy together.
- [ ] Each service owns its store; no shared tables.
- [ ] Every remote call has a timeout, bounded retry with backoff and jitter, and a defined failure behavior.
- [ ] Sync chains are short; no chatty loops; cross-service transactions use sagas with compensation.
- [ ] Trace/correlation IDs propagate through calls and events; per-service metrics and alerts exist.
- [ ] APIs and event schemas are versioned; consumers tolerate unknown fields.
- [ ] Service-to-service authentication; gateway replicated and logic-free.

Reviewing event-driven or pub/sub:
- [ ] Consumers are idempotent; duplicates and reordering are handled.
- [ ] Partition or ordering key chosen deliberately; retry limits and a dead-letter queue with alerting.
- [ ] Someone can trace one business flow end to end (`event-driven.md`).

Reviewing serverless:
- [ ] Time, memory, payload and concurrency limits checked against the workload.
- [ ] Cold-start impact measured on latency-sensitive paths; connections to databases bounded.
- [ ] Handlers idempotent and stateless; business logic separable from the platform.
- [ ] Least-privilege roles, secrets managed, event payloads validated.

Reviewing state:
- [ ] State location is stated for every kind of data (token, cache, DB, memory).
- [ ] No per-instance state that would break with two instances; sticky sessions only as a documented stopgap.
