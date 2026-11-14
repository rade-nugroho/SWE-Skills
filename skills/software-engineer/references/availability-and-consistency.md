# Availability and consistency

Use this when a task states an uptime target, adds replicas, failover, caches or regions, splits a write across services, or asks "is stale data OK here?". Code-level techniques (timeouts, retries, idempotency keys, circuit breakers) live in [fault-tolerance.md](fault-tolerance.md); MTTF/MTBF/MTTR formulas and growth models in [reliability.md](reliability.md); overall design flow in [system-design.md](system-design.md). Related: `database-design.md` (replication, sharding), `distributed-systems.md` (consensus), `load-balancing.md`, `event-driven.md`, `security.md` (backup, disaster recovery).

## Contents
1. Availability: nines, composition, how it differs from reliability
2. High-availability techniques and finding a SPOF
3. Consistency models, strong to eventual
4. Consistency mechanisms and when to use each
5. CAP and PACELC
6. Requirement to choice table
7. Maintainability
8. Design-review checklist

## 1. Availability

`A = uptime / (uptime + downtime) = MTTF / (MTTF + MTTR)`; see reliability.md for the metric definitions. Allowed downtime `= (1 − A) × period`.

| Target | Per year | Per month (30.4 d) | Per day |
|---|---|---|---|
| 99% | 3.65 d | 7.3 h | 14.4 min |
| 99.9% | 8.77 h | 43.8 min | 1.44 min |
| 99.95% | 4.38 h | 21.9 min | 43.2 s |
| 99.99% | 52.6 min | 4.38 min | 8.64 s |
| 99.999% | 5.26 min | 26.3 s | 0.86 s |

Each extra nine cuts the budget tenfold, and cost and operational effort rise with it. At 99.99% and above a human cannot respond in time: detection, failover and rollback have to be automatic.

Composition (assumes independent failures, which is optimistic; shared config, deploys, and a shared dependency fail together):
- Series, all required: `A = A1 × A2 × …` (always below the weakest link).
- Parallel, any one suffices: `A = 1 − (1 − A1)(1 − A2)…`.

Worked example: load balancer 99.99%, app tier 99.9%, database 99.95%.
- All single: 0.9999 × 0.999 × 0.9995 = 0.99840, about 99.84%, roughly 14 h down per year.
- App ×2 in parallel: 1 − 0.001² = 0.999999. Database primary + replica: 1 − 0.0005² = 0.99999975. Load balancer still single:
  0.9999 × 0.999999 × 0.99999975 = 0.999899, about 99.99%, roughly 53 min per year.
- The single load balancer is now almost the whole budget. Pairing it too (1 − 0.0001² = 0.99999999) gives about 0.9999987, roughly 40 s per year on paper. Real numbers will be worse: failover is not instant or perfect, and the pair shares config.
- Five 99.9% services called in series give 0.999⁵ ≈ 99.5%: a chain of dependencies erodes the target quickly. Make non-critical calls optional (degrade, section 2).

| | Availability | Reliability | Fault tolerance |
|---|---|---|---|
| Question | is it usable right now? | does it run correctly without failing for a period? | does it keep working when parts fail? |
| Measured by | uptime %, nines | MTTF/MTBF, failure rate, error rate | whether a component loss is visible to users |
| Improved by | redundancy, fast detection, fast recovery (low MTTR) | fewer defects, testing, capacity headroom | redundancy, isolation, retries, failover |
| Example | 99.9% monthly | one failure per 500 h | a node dies, users notice nothing |

They interact: a system can be available but unreliable (fails often, recovers in seconds) or reliable but unavailable (rarely fails, but a restore takes a day). Lowering MTTR is usually cheaper than raising MTTF.

## 2. High-availability techniques

| Technique | What it does | Watch out for |
|---|---|---|
| Redundancy (N+1 or more) | spare capacity so one loss is absorbed | spares must carry the load: N+1 sized at 100% utilization has no headroom |
| Active-passive (hot or warm standby) | one serves, a standby takes over | failover time (seconds to minutes), replication lag means lost recent writes, standby never tested |
| Active-active | all serve at once, load shared | state: conflicting writes, session handling; needs load balancing (`load-balancing.md`) |
| Health checks | remove bad instances automatically | shallow checks (port open) pass while the app is broken; deep checks that hit a shared DB can take everything out at once |
| Multi-zone | survive a data-centre loss | cross-zone latency, replica placement, cross-zone data cost |
| Multi-region | survive region loss, serve users nearby | consistency across regions (section 5), cost, failover runbook |
| Graceful degradation | drop optional features instead of failing | decide in advance which features are optional; test the degraded mode |
| Fast rollback / canary | shortens bad-deploy outages | schema changes that cannot be rolled back |
| Capacity headroom + load shedding | avoid overload turning into an outage | see rate limits and back-pressure in fault-tolerance.md |

Failover details that decide the outcome: how it is detected (heartbeat timeout vs. false alarms), who decides (automated election vs. a person), the split-brain risk (two nodes both believe they are primary; fence the old one and use a quorum or lease, see `distributed-systems.md`), and what the promoted replica is missing (async lag). Fail over on a schedule in a test environment; an untested failover path is a guess.

### Finding a single point of failure on a diagram
1. List every box and arrow on the request path, plus the things off the path that the path needs: DNS, certificates, config service, secrets store, auth provider, CI/CD, queue, cache, scheduler.
2. For each, ask "if this alone disappears, what stops?" If the answer is "everything" or "all writes", it is a SPOF.
3. Check count: one instance is a SPOF. Two instances in the same rack, zone, account, or deploy unit share a fate: redundancy needs separate failure domains.
4. Check state: stateless tier behind a load balancer is easy; a single primary database, a single leader, a single-writer file, or a local disk is the usual survivor.
5. Check the redundancy itself: load balancers, API gateways, and the failover controller can be the SPOF. Check that the standby has capacity, current data, and a tested promotion path.
6. Check shared dependencies: one external API, one region, one third-party DNS provider, one cron host.
7. Write the result in the design doc as a table: component, failure effect, mitigation, accepted risk.

## 3. Consistency models, strong to eventual

"Consistency" here means what a client can observe when data is replicated or cached. It is not the C in ACID (constraints hold after a transaction). Pick the weakest model the requirement tolerates; each step down buys latency and availability.

| Model | What the user can observe | Typical cost | Enough for |
|---|---|---|---|
| Linearizable (strong) | every read sees the latest completed write; behaves like one copy in real-time order | coordination on each op (consensus or sync replication), higher latency, unavailable on the minority side of a partition | account balance, unique username claim, leader lock, inventory last-unit decrement |
| Sequential | all clients see operations in one same order, which need not match wall-clock time | cheaper than linearizable, but rarely offered by itself | replicated log consumers that only need the same order |
| Causal | if B was written after reading A, nobody sees B without A; unrelated writes may appear in any order | track dependencies (vector clocks or version metadata) | comments and replies, chat, collaborative edits |
| Read-your-writes | you always see your own writes; others may lag | route reads to the primary or a session-pinned replica, or pass a version token | profile edit, posting a comment, "save" then reload |
| Monotonic reads | your reads never go back to older data | pin a client to one replica or track the last version seen | paging through a feed, dashboards that must not flicker backward |
| Eventual | replicas converge if writes stop; reads can be stale or out of order meanwhile | cheapest, highest availability | like counts, view counts, search index, caches, DNS |

Symptoms to expect and test for under weaker models: a user saves and then sees old data (needs read-your-writes); a refresh shows older data than before (needs monotonic reads); a reply appears before its parent (needs causal order); two concurrent writes to the same key, last one silently wins (needs a conflict strategy, section 4).

Practical rule: eventual consistency per se is not a plan. State which session guarantees you add on top (usually read-your-writes plus monotonic reads) and the maximum staleness you accept, as a number ("replica lag under 5 s at p99").

## 4. Consistency mechanisms and when to use each

| Mechanism | How it works | Use when | Cost / pitfall |
|---|---|---|---|
| Single-leader replication, synchronous | the leader waits for replicas to confirm a write | no lost acknowledged writes, strong reads from leader | write latency; one slow replica stalls writes (use semi-sync: one or two sync replicas) |
| Single-leader replication, asynchronous | leader acknowledges first, replicas catch up | read scaling, tolerate small staleness | replication lag: stale reads; failover can lose the last writes |
| Quorum (N replicas, write to W, read from R) | `R + W > N` makes every read set overlap the latest write set | tunable consistency per operation, leaderless stores | N=3, W=2, R=2 tolerates one node down for both; W=1, R=1 is eventual; sloppy quorums and clock skew weaken the guarantee; overlap alone is not full linearizability |
| Two-phase commit (2PC) | coordinator asks all participants to prepare, then commits or aborts | atomic write across a few databases you control, low latency between them | blocks if the coordinator dies after prepare; locks held; poor fit across slow or third-party services |
| Saga | sequence of local transactions with a compensating action for each step | multi-service workflow (order, payment, shipping) | intermediate states are visible; compensations must be idempotent and may themselves fail; needs a durable state log (see `event-driven.md`) |
| Outbox + idempotent consumer | write data and the event in one local transaction; publisher relays it; consumers dedupe | "update DB and publish event" without 2PC | duplicates and delay: consumers must be idempotent (fault-tolerance.md) |
| Consensus (Raft, Paxos) | replicas agree on an ordered log through majority votes | leader election, config, coordination, strongly consistent stores | needs a majority alive; latency of a round trip; see `distributed-systems.md` |
| Read repair / anti-entropy | fix stale copies on read, or compare replicas in background | eventual stores | repair lag; deletes need tombstones |
| Conflict resolution: last-write-wins | highest timestamp wins | data where losing an update is fine | silently drops concurrent writes; clock skew picks the wrong winner |
| Conflict resolution: version vectors + merge | detect concurrent writes, merge in application code or ask the user | carts, documents, multi-device sync | merge logic is real code that needs tests |
| CRDTs | data types (counters, sets, registers, text) whose merge is commutative and idempotent | multi-writer offline or multi-region data, collaborative editing | restricted operations; metadata growth; no invariants like "never negative" |
| Cache invalidation (TTL, write-through, event-based) | keep a derived copy fresh | read-heavy data | stale window equals your TTL; stampedes (system-design.md) |

Choosing between 2PC and saga: if all participants are in one database or a tightly managed cluster, use a plain transaction. If the work spans services, prefer a saga with compensation plus idempotency, and show the user a "pending" state rather than pretending it is atomic.

Code checks when you add replicas or caches:
- Which reads must hit the primary (after-write reads, balance checks)? Mark those call sites explicitly.
- Does any code read a replica and then write based on it (read-modify-write)? Use a version column or conditional update (`UPDATE ... WHERE version = ?`), or do both on the primary.
- Where two writers can touch one key, write down the conflict rule.
- Tests: inject replica lag and a stale cache entry, and assert the user-visible behavior.

## 5. CAP and PACELC

CAP: when the network partitions, a replicated system chooses between
- Consistency (here: linearizable reads: every read returns the latest write or an error), or
- Availability (every non-failed node answers, possibly with stale data).
Partition tolerance is not optional in a distributed system: partitions happen, so the real choice is C or A during one. Without a partition you can have both.

| During a partition | Behavior | Examples (depend on configuration) |
|---|---|---|
| CP | minority side rejects or blocks requests; no stale reads | ZooKeeper, etcd, Spanner, HBase; MongoDB with majority concerns |
| AP | every node keeps serving, may return stale data; reconcile later | Cassandra and DynamoDB at low consistency levels; Riak; DNS |

Common misreadings:
- "Pick any two": wrong, P is forced; the choice only bites during a partition.
- "A database is CP or AP": most are tunable per operation (quorum levels, read concern), so classify the operation, not the product.
- "CA systems exist": only as a single-node or never-partitioned setup; not a distributed choice.
- CAP availability means every node answers, a stronger claim than "99.9% uptime". A CP system with a majority alive is still highly available overall.
- CAP consistency (linearizability) is not ACID consistency and not eventual consistency.
- CAP says nothing about latency; PACELC covers that.

PACELC: if Partition, choose Availability or Consistency; Else (normal operation), choose Latency or Consistency. Even with no partition, waiting for replicas to confirm costs latency. Typical labels: Dynamo-style stores PA/EL (fast and available, weaker reads); Spanner-like stores PC/EC (consistent always, pay in latency); stores with tunable levels sit in between. Use this to justify why a multi-region design that is "fine most of the time" still has a latency bill for strong writes (cross-region round trips are ~100 ms or more).

## 6. Requirement to choice

| Data / requirement | Consistency needed | Typical choice |
|---|---|---|
| Money, ledgers, balances | linearizable per account; no lost or doubled writes | single-leader relational DB with transactions; idempotency keys; saga with compensation across services; CP side of CAP |
| Inventory, seat booking, unique constraints | strong for the contended item | conditional update or row lock on the primary; reservation with expiry; oversell policy if you choose AP |
| Orders, payment status | strong writes, reads can follow with read-your-writes | primary for writes and after-write reads; async replicas for history lists |
| Social feeds, timelines | eventual | async replicas, fan-out via queue; monotonic reads per session |
| Likes, view counts, metrics | eventual, approximate OK | counters batched or CRDT counter; accept small drift |
| User profile, settings | read-your-writes | session-pinned reads or version token; replicas otherwise |
| Sessions, auth tokens | read-your-writes; revocation must propagate quickly | shared store (Redis) with replication; short TTL tokens; accept brief revocation lag or check a denylist on the primary |
| Chat, comments, collaboration | causal; merge for concurrent edits | causal ordering metadata, CRDT or operational transform |
| Search index, caches, CDN | eventual, bounded staleness | TTL plus event-based invalidation; source of truth elsewhere |
| Leader election, locks, config | linearizable | consensus store (etcd, ZooKeeper); lease with fencing token |
| Multi-region active-active | depends on item | strong for money/inventory (home region owns the key), eventual with CRDT or merge for the rest |

If a table row does not fit, ask the product owner what the user may see and for how long, then pick the model from section 3.

## 7. Maintainability

Maintainability is how cheaply the system can be changed, fixed and operated. Poor maintainability shows up as availability loss: slow diagnosis (high MTTR), risky deploys, and fear of change.

| Quality | What it looks like | Check |
|---|---|---|
| Modularity | small components with one responsibility, low coupling, high cohesion, clear interfaces | can one module be changed or replaced without touching others? |
| Observability | structured logs with request IDs, metrics (rate, errors, latency, saturation), traces across services, alerts tied to user impact | can you find the failing component from a single request ID in minutes? |
| Operability | health endpoints, config outside code, runbooks, safe restart, graceful shutdown, feature flags | can on-call act at 3 a.m. without the author? |
| Deploy and rollback | automated pipeline, small releases, canary, one-step rollback, backward-compatible migrations (expand, migrate, contract) | what is the rollback time, and has it been rehearsed? |
| Documentation | architecture and data-flow diagram, API contracts, decision records, dependency list, runbooks, kept next to the code | is there a doc for each failure the SPOF table lists? |
| Testability | automated unit, integration and regression tests; fault-injection tests for failure paths | does a failing dependency have a test? |
| Changeability | no duplicated logic, limited technical debt, code review, regular refactoring | what does a typical change touch? |

Useful indicators (treat as hints, not goals): cyclomatic complexity, duplication, test coverage, change failure rate, time to restore service after an incident. MTTR is repair time; "time to change" is a separate measure, do not mix them.

Checklist:
- [ ] Each service has structured logs, the four golden metrics and at least one alert tied to user impact
- [ ] Every deploy can be rolled back in minutes; DB migrations are backward compatible
- [ ] Config and secrets are outside the code and changeable without a rebuild
- [ ] Runbook exists for each known failure mode and each SPOF
- [ ] Architecture doc and API contract are current
- [ ] Failure paths and degraded modes have tests

## 8. Design-review checklist

Requirements
- [ ] Availability target stated as a number with a measurement window; downtime budget computed (section 1)
- [ ] Per-data-class consistency requirement stated, with allowed staleness in seconds
- [ ] RTO and RPO for a lost node, zone and region stated (see `security.md` for backups and disaster recovery)

Availability
- [ ] SPOF table done (section 2); every critical component has two or more instances in separate failure domains
- [ ] Composite availability computed for the critical path; dependencies in series reviewed
- [ ] Failover is automatic or has a rehearsed runbook; split-brain handled; failover tested in the last quarter
- [ ] Health checks are deep enough to catch broken apps, not so deep they cascade
- [ ] Degraded modes defined: what turns off first, and what the user sees
- [ ] Capacity survives the loss of one zone without overload

Consistency
- [ ] Each write path names its consistency model and mechanism (leader, quorum, saga, CRDT)
- [ ] Read-after-write call sites go to the primary or carry a version token
- [ ] Concurrent write conflicts have a defined rule; last-write-wins used only where lost updates are acceptable
- [ ] Multi-service writes use a saga or outbox with idempotent steps, not an unexamined distributed transaction
- [ ] Partition behavior chosen per operation (CP or AP) and written down; tests simulate lag and partition
- [ ] Latency cost of the strong paths measured against budget

Operations
- [ ] Maintainability checklist (section 7) passes
- [ ] Alerts, dashboards and on-call ownership exist before launch
- [ ] Single-region and single-vendor risks are listed and either mitigated or explicitly accepted
