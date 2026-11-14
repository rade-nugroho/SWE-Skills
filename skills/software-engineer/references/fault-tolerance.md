# Fault tolerance

Use this when code calls things that can fail (network, DB, files, third-party APIs), runs for a long time, handles money/orders, or when a design has availability targets.

Two families:
- **Fault removal / recovery** — detect the error, then recover: *backward* (roll back to a known-good state) or *forward* (correct the current state and continue).
- **Fault masking** — redundancy plus voting/failover, so the caller never sees the fault.

Fault tolerance adds complexity, cost, and new failure modes. Apply it where a requirement (availability, durability, correctness of money) calls for it, not everywhere.

## Code-level techniques

| Technique | What it is | Use when |
|---|---|---|
| Exception handling (forward recovery) | catch a specific error where you can do something meaningful about it; otherwise let it propagate | always — but never swallow errors silently or catch-all to hide bugs |
| Transactions (backward recovery) | all-or-nothing state change; roll back on error | multiple writes that must stay consistent |
| Checkpoint + rollback/resume | save progress periodically; restart from last checkpoint | long-running jobs, batch backfills, imports |
| Recovery block | run primary → check result with an acceptance test → on failure, restore state and run an alternate (fallback) | there's a simpler/safer fallback and some extra latency is OK (e.g. cached/default value when a recommender fails) |
| Timeouts | bound every remote call | always on network calls — a missing timeout turns a slow dependency into an outage |
| Retries with exponential backoff + jitter | retry transient failures a few times | idempotent operations, transient errors only (5xx, timeouts), never on 4xx/validation errors |
| Idempotency keys | the same request applied twice has the effect of once | retried writes, payments, message consumers (at-least-once delivery) |
| Circuit breaker | stop calling a failing dependency for a while; fail fast | a dependency that can be down for a while, to avoid piling up threads/requests |
| Compensation / saga (forward recovery) | undo earlier steps with compensating actions | multi-service workflows that can't share one transaction |
| Validation + assertions | detect bad state early, at boundaries | inputs from users, other services, files |

## System-level techniques

- **Redundancy / replication** — multiple instances and replicas across zones; no single point of failure on the critical path.
- **Isolation / bulkheads** — separate pools, processes, or services so one failure doesn't sink everything.
- **Graceful degradation** — serve a reduced experience (stale cache, feature off) instead of an error.
- **Load balancing + health checks** — route around unhealthy instances.
- **Failure prediction / monitoring** — alerts on error rate, latency, saturation before users notice.
- **N-version programming / voting** — independently built versions vote on the result. Expensive; reserved for safety-critical systems. Rarely appropriate in typical product code.
- **Backups + tested restore** — a backup you've never restored is not a backup.

## Checklist for code that touches unreliable dependencies

- [ ] Every remote call has a timeout
- [ ] Retries only on transient errors, bounded, with backoff + jitter, only for idempotent operations
- [ ] Writes that may be retried are idempotent
- [ ] Multi-step state changes are transactional or have compensation
- [ ] Errors are handled where they can be acted on, logged with context, never silently swallowed
- [ ] There is a defined behavior when the dependency is down (fail fast, fallback, or degrade)
- [ ] Failure paths have tests (simulate timeout / error from the dependency)
