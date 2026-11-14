# Scalability

## Contents
1. What scalability means
2. Vertical vs horizontal scaling
3. Choosing an approach
4. Design principles
5. Bottlenecks: symptom to fix
6. Code-level scalability review (run on a diff)
7. Measure first, then plan capacity
8. Checklist

Related: `system-design.md` (building blocks, estimation), `load-balancing.md`, `caching.md`, `database-design.md` (replication, sharding), `availability-and-consistency.md`, `api-gateway-queues-rate-limits.md`, `testing.md` (load and stress tests), `metrics.md`.

## 1. What scalability means

A system is scalable when it keeps meeting its performance target as demand grows, and growing it costs roughly in proportion to the growth. "Handles more" is not enough: if doubling traffic needs 10x the money or a rewrite, it does not scale well. Always state the target ("p95 < 200 ms") before asking whether something scales.

| Dimension | Grows with | Typical failure | First thing to check |
|---|---|---|---|
| Load | requests/s, concurrent users, jobs | latency climbs, errors, timeouts | per-request cost, saturation of CPU/DB/pool |
| Data | rows, bytes, retention, index size | queries slow down, backups and migrations take hours | access patterns, indexes, archival, partition key |
| Geography | users in more regions | high round-trip time, data-residency issues | CDN, regional replicas, where writes must go |
| Team | engineers, services, deploys per day | merge conflicts, slow builds, unclear ownership | module boundaries, independent deploys, CI time |

Most tasks touch load and data. Raise geography and team only when the requirements mention them. Splitting into microservices to fix a team problem adds load-side costs (network hops), so name which dimension you are solving.

## 2. Vertical vs horizontal scaling

| | Vertical (scale up) | Horizontal (scale out) |
|---|---|---|
| What | bigger machine: more CPU, RAM, disk | more machines or instances behind a balancer |
| Code changes | usually none | service must be stateless; data must be partitioned or replicated |
| Ceiling | largest available machine | far higher, bounded by coordination cost |
| Availability | one box is a single point of failure, resize may need downtime | losing one node is survivable if capacity has headroom |
| Complexity | low | higher: deploys, config, consistency, debugging across nodes |
| Cost shape | price per unit rises steeply at the top end | roughly linear, plus ops overhead |
| Good fit | databases early on, small or steady load, quick fix | web/API tiers, workers, caches, high or spiky load |
| Typical cap | memory, core count, single-disk IOPS | shared state (the DB), coordination, hot keys |

Most real systems mix both: stateless app tier scaled out, primary database scaled up, then read replicas, then sharding.

## 3. Choosing an approach

Rule of thumb: **scale up first, then out**. Moving to a bigger instance is often a config change; going horizontal is a design change. Leave the simple path when one of these is true: the largest affordable machine is within reach, you need redundancy anyway, load is spiky enough that fixed big boxes sit idle, or the single machine cannot be restarted without unacceptable downtime.

| Situation | Lean toward | Why |
|---|---|---|
| Steady, modest load; team is small | vertical, plus fix hot queries | cheapest in effort |
| Stateless API with growing traffic | horizontal (2+ instances behind a balancer) | easy once state is out of the process |
| Relational DB at its limit | in order: tune queries and indexes, cache, vertical, read replicas, then sharding | each step costs more complexity than the last |
| Spiky or unpredictable traffic | horizontal with autoscaling, or serverless | pay for peaks only when they occur |
| Latency complaint | find the bottleneck first (section 7) | more servers do not fix a slow query or a distant database |
| Need survive-one-failure | at least 2 instances in separate zones | availability, not throughput, drives the count |

**What makes a service horizontally scalable**
- No per-user state in process memory or on local disk: sessions, uploads, and caches live in a shared store (Redis, DB, object storage) or in signed tokens.
- Any instance can serve any request; the balancer needs no stickiness.
- Config comes from the environment, not local files; start-up is fast and idempotent.
- Background jobs are safe to run on many nodes at once (queue consumers, leases, or a leader for singleton jobs like schedulers).
- Shared resources can absorb N instances: DB connection limits, third-party rate limits, and file locks are the usual surprises.
- Shutdown is graceful: finish or hand back in-flight work on SIGTERM.

**Autoscaling signals** (pick the one that tracks saturation of your bottleneck)
- CPU utilization: fine for compute-bound services; a poor signal for I/O-bound ones.
- Request rate or concurrency per instance: tracks load directly.
- Queue depth or message age: best for workers; scale on backlog, not CPU.
- Latency (p95): a lagging signal; use as a guard, not the primary trigger.
- Set min (for availability), max (for cost and downstream limits), a scale-out threshold well below saturation (about 50-70%), and a cooldown to stop flapping. Slow start-up or cold starts mean scale earlier or keep warm capacity.

## 4. Design principles

| Principle | In practice | Cost or trap |
|---|---|---|
| Statelessness | externalize session and cache state | extra network hop per lookup |
| Partitioning (sharding) | split data by a key that matches the main access pattern | hot partitions, cross-shard queries, resharding pain |
| Async work | queue what the user need not wait for: email, thumbnails, reports, webhooks | eventual results, retries, need for idempotent consumers |
| Caching | cache read-heavy, slow-to-compute, rarely-changing data at the right layer | invalidation, stampedes, stale reads |
| Replication | read replicas for read scale; standby for failover | lag means stale reads; replicas do not scale writes |
| Backpressure | bound queues and concurrency; reject or slow callers (429/503) instead of accepting unlimited work | needs client retry with backoff and jitter |
| Loose coupling | talk through APIs/events; no shared tables between services; timeouts and circuit breakers on remote calls | more moving parts; contracts to version |
| Do less per request | batch, paginate, precompute, return only needed fields | precomputed data can go stale |

Prefer removing work over adding machines: an index or a cache hit is cheaper than another node. Details: `caching.md`, `database-design.md`, `api-gateway-queues-rate-limits.md`, `fault-tolerance.md`.

## 5. Bottlenecks: symptom to fix

The bottleneck is the resource that saturates first, not necessarily the slowest component. Fix it, re-measure, then look for the next one.

| Area | Symptom | Likely cause | Confirm with | Fix |
|---|---|---|---|---|
| Database queries | p95 grows with data size; DB CPU high | missing index, full scans, N+1, bad join | slow-query log, `EXPLAIN`, query count per request | add or fix index, batch/join, cache hot reads |
| DB connections | timeouts "no connection available", DB at max connections | pool too small or too large x many instances, leaked connections | pool wait time, DB active connections | size pools against DB limit, add a pooler, close on all paths |
| DB writes | write latency up, replication lag, lock waits | single primary, hot rows, big transactions | lock-wait metrics, replica lag, write IOPS | shorter transactions, batch writes, queue writes, shard |
| App code (CPU) | CPU pegged, latency tracks load | inefficient algorithm, serialization, regex, tight loops | CPU profiler / flame graph | better algorithm, cache result, move work off hot path |
| Memory | rising RSS, GC pauses, OOM kills | unbounded collections or caches, leaks, large payloads | heap profile, GC logs, memory over time | bound sizes, stream, evict, fix leak |
| Network | high latency, bandwidth near cap, retransmits | chatty calls, large payloads, distant region | per-hop traces, bytes in/out, RTT | batch calls, compress, CDN, co-locate, trim fields |
| Single point of failure | one node's loss takes the service down | one instance, one DB, one balancer, one zone | architecture review, kill-a-node test | redundancy across zones, failover, health checks |
| Synchronous chain | latency = sum of all hops; one slow dependency stalls everything | long call chain, no timeouts | distributed traces, dependency latency percentiles | async handoff, parallel calls, timeouts, circuit breaker, cache |
| Locks and contention | throughput flat or falls as threads/instances grow; CPU low but latency high | global lock, hot row, shared counter, synchronized block | thread dumps, lock-wait stats, contention profile | shrink critical section, shard the lock or counter, optimistic concurrency |
| Storage I/O | high disk wait, slow reads and writes | random I/O, undersized volume, big scans | iostat/disk latency, IOPS vs provisioned | faster disk, better access pattern, caching, partitioning |
| Third-party service | slowness or errors only on calls to a vendor; 429s | vendor limit, no timeout, retried on failure | outbound call latency and error rate | cache, queue, rate-limit self, backoff, fallback |
| Auth path | login or token checks dominate at peaks | per-request remote lookup, slow hashing on hot path | trace spans for auth | cache validation results, verify tokens locally, scale the auth service |
| Thread/worker exhaustion | requests queue though CPU is idle | blocking I/O on limited threads | thread pool queue depth, saturation | async I/O, bigger pool only if downstream can take it, bulkheads |

## 6. Code-level scalability review (run on a diff)

For each changed path, ask: what happens at 100x the data and 10x the traffic?

| Check | Look for | Fix |
|---|---|---|
| N+1 queries | query inside a loop or per-item lazy load | join, `IN (...)` batch, eager load |
| Missing index | new `WHERE`, `ORDER BY`, join, or FK column with no index in the migration | add index matching the filter and sort order |
| Unbounded query | no `LIMIT`, `SELECT *`, filter that can match everything | limit, select needed columns |
| No pagination | list endpoint returns all rows; offset pagination on huge tables | cursor/keyset pagination, max page size |
| Unbounded in-memory collection | reading a whole file/table into a list; growing map or cache without eviction | stream, iterate in chunks, bounded cache with TTL |
| Blocking call on hot path | sync HTTP, disk, or sleep in request handler; CPU-heavy work in event loop | async I/O, offload to a worker or queue |
| Chatty remote calls | many small calls to one service per request | batch endpoint, one query, cache, parallelize |
| Per-request expensive setup | new DB/HTTP client, regex compile, config load, TLS handshake per request | create once, reuse, pool |
| Global lock or shared mutable state | one mutex, a static counter, a singleton with synchronization | partition, atomic or sharded counters, immutable data |
| Unbounded queue or retry | queue with no max size; retry loop with no limit, backoff, or jitter | bound size, drop or reject, capped retries with backoff and jitter, dead-letter queue |
| Read-modify-write races | check-then-act on shared data | transaction, unique constraint, atomic update |
| Work in the request that can wait | email, PDFs, fan-out, reports done inline | enqueue with an idempotency key |
| Missing timeouts | remote call without a timeout | explicit timeout on every outbound call |
| State in the process | session, upload, or cache held in local memory/disk | shared store |
| Hot key | all traffic to one id, tenant, or partition key | key salting, local caching, better key choice |

Report findings with the data size or request rate at which each would hurt, not just "this is slow".

## 7. Measure first, then plan capacity

**Do not optimize on a guess.** Loop: define target, measure, find the bottleneck, change one thing, re-measure.
- **Percentiles, not averages.** Track p50, p95, p99, plus error rate and throughput. Averages hide tail latency.
- **Load test** at expected and peak traffic with realistic data volume and request mix; **stress test** past peak to see where it breaks and whether it recovers (`testing.md`). Check that adding an instance really adds capacity.
- **Profile** the saturated resource: CPU profiler, heap profile, slow-query log, distributed traces.
- **Watch saturation** (CPU, memory, pool use, queue depth, disk), not only latency (`metrics.md`).
- Run on production-like data; an index that works on 1,000 rows may not on 100 million.

**Capacity arithmetic**
- Average rps = requests/day / 86,400. Peak = average x peak factor (2-10x; measure it).
- Concurrency (Little's law) = rps x average latency in seconds.
- Instances = peak rps / (measured per-instance rps x target utilization), rounded up, then add headroom for a failed node (N+1) or a zone.
- Storage = rows/day x bytes/row x retention, plus index and replica overhead; project 12-24 months.
- Check the shared limits too: DB connections = instances x pool size.

**Worked example.** An API gets 50M requests/day; a load test shows one instance sustains 400 rps before p95 breaks the target.
1. Average = 50,000,000 / 86,400 ≈ 580 rps. Peak factor 5 → ≈ 2,900 rps.
2. Run instances at 60% of tested capacity: 400 x 0.6 = 240 rps each.
3. 2,900 / 240 ≈ 12.1 → 13 instances; add one for N+1 → 14.
4. Pool of 20 per instance → 14 x 20 = 280 connections; confirm the DB allows that, or add a pooler.
5. At 0.1 s latency, each instance handles about 240 x 0.1 = 24 concurrent requests; check thread or worker settings match.
6. If it writes 2M rows/day at 1 KB: about 2 GB/day, roughly 0.73 TB/year before indexes and replicas.

State the inputs (peak factor, tested rps) in the design doc so they can be re-checked.

## 8. Checklist

- [ ] Scalability target stated with numbers and the dimension (load, data, geography, team).
- [ ] Bottleneck identified by measurement, not assumed.
- [ ] Scale-up options tried before scale-out; reason recorded if skipped.
- [ ] App tier is stateless; shared state is in a store built for it.
- [ ] Queries have indexes, limits, and pagination; no N+1.
- [ ] No unbounded collections, queues, or retries; backpressure defined.
- [ ] Slow or optional work moved off the request path.
- [ ] Every remote call has a timeout; long sync chains broken up or guarded.
- [ ] No single point of failure for the critical path, or it is called out as a known risk.
- [ ] Shared limits (DB connections, vendor rate limits) checked against instance count.
- [ ] Autoscaling signal, min, max, and cooldown chosen if autoscaling is used.
- [ ] Load test run at peak and beyond, with p95/p99 and saturation metrics reviewed.
- [ ] Capacity estimate written with inputs and headroom; revisit date set.
