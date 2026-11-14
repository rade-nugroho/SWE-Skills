# Caching, latency and throughput

## Contents
1. Latency vs throughput
2. Should you cache at all, and where
3. Caching strategies
4. Invalidation
5. Eviction policies
6. Distributed caches and a design outline
7. Edge caching, CDN vs edge server
8. Cold vs warm cache
9. Failure modes and mitigations
10. Checklist for adding a cache in code

Related: `system-design.md` (building blocks), `load-balancing.md` (consistent hashing), `networking.md` (DNS caching, TTL, CDN basics), `database-design.md` (Redis), `scalability.md`, `availability-and-consistency.md`, `fault-tolerance.md`.

## 1. Latency vs throughput

- **Latency**: time one request takes, from send to complete response. **Throughput**: work finished per unit time (req/s, tx/s, MB/s). One is per-task time, the other is a rate.
- They are linked but not opposites. Parallelism raises throughput without lowering per-request latency. Queuing links them: as load nears capacity, latency climbs sharply. Past saturation, throughput flattens while latency keeps growing.
- **Where latency comes from**: network (distance, hops, TLS/DNS setup, congestion), queuing (waiting for a thread, connection or lock), processing (CPU, serialization), storage (disk, slow queries, N+1), and downstream calls, which add up in series.
- **Report percentiles, not averages.** An average hides the slow tail: a 100 ms mean can contain requests taking 1-2 s. Use p50 (typical), p95 and p99 (the tail users notice). Fan-out makes tails worse, since a page calling 10 backends hits one slow tail often. Write targets as "p99 < 300 ms at 500 req/s", never "fast".
- **Measure** with load tests at realistic concurrency, APM/tracing for per-hop time, histograms in metrics (not mean gauges), and profilers for CPU hot spots. Ping/traceroute only cover the network leg.

| Goal | Levers |
|---|---|
| Lower latency | cache, move data or compute closer to users (CDN/edge/region), fix slow queries and indexes, fewer round trips (batching, fewer sequential calls), connection reuse, compress/shrink payloads, do slow work async |
| Raise throughput | horizontal scale behind a load balancer, parallelism, batching, connection pools, async/queued work, faster code on the hot path, cache to cut backend load |

Before optimizing, find the dominant component with a trace. Caching a 5 ms step inside a 900 ms request changes nothing.

## 2. Should you cache at all, and where

Cache when all three hold, and you have measured it:
1. The data is **read far more than written** (or the same result is requested repeatedly).
2. It is **expensive** to produce (slow query, remote call, heavy compute) or the source is a bottleneck.
3. The product **tolerates staleness** for some stated window.

Skip or delay a cache when: reads are mostly unique keys (hit rate near zero), data must be strictly current (balances, inventory at checkout), the real fix is a missing index, or the data is cheap to compute. A cache adds a consistency bug surface, so it needs a reason.

| Layer | What it holds | Good for | Watch out for |
|---|---|---|---|
| Browser/client | HTTP-cached responses, local storage | static assets, rarely changing API data | cannot be purged by you; use versioned URLs and sane `Cache-Control` |
| CDN / edge | static files, cacheable responses near users | global users, media, public pages | purge delay, personalized or private content |
| Reverse proxy (nginx, Varnish) | whole responses in front of the app | public GETs, absorbing spikes | cache key must include `Vary` dimensions |
| Application in-process | objects in the app's memory | tiny hot data, config, parsed results; no network hop | one copy per instance, so copies diverge; memory pressure; lost on restart |
| Distributed cache (Redis, Memcached) | shared key-value data | sessions, query results, computed objects across instances | extra network hop, an extra system to run, failure behavior |
| Database | buffer pool, query cache, materialized views | already there; tune before adding more | not a substitute for app-level design |

Prefer the layer closest to the user that still gives correct data. Layers stack: each one adds staleness, so know the total worst case (browser TTL + CDN TTL + app TTL).

## 3. Caching strategies

| Strategy | Read/write flow | Consistency | Failure and cost trade-offs |
|---|---|---|---|
| **Cache-aside** (lazy loading) | App checks cache; on miss reads DB, writes cache, returns. Writes go to DB, then delete or update the cache entry. | Stale until invalidated; races possible between a read-fill and a write | Default choice. Cache outage just means slower reads. First read per key is slow. App owns all the logic. |
| **Read-through** | App talks only to the cache; the cache layer loads from the DB on a miss | Same as cache-aside | Simpler app code; needs a cache provider or library that supports loaders. Cache down means reads fail unless you add a fallback. |
| **Write-through** | Write goes to cache and DB together, synchronously | Cache matches DB after each write | Write latency is the sum of both; caches data that may never be read. A failure between the two writes needs handling. |
| **Write-behind** (write-back) | Write goes to cache, flushed to DB later in batches | DB lags cache | Fast writes and batching, but **data loss if the cache dies before flush**. Needs durable queueing, ordering and retries. Use only when loss is tolerable or the cache is durable. |
| **Refresh-ahead** | Cache refreshes hot entries before they expire | Fresher for hot keys | No latency spike at expiry; wasted loads if predictions are wrong. Good for known hot keys, an overkill for the long tail. |

Default to cache-aside with TTL. Note the source page only describes cache-managed vs app-managed loading; the five names above are the standard forms.

## 4. Invalidation

Invalidation is the hard part: the cache is a copy, and every code path that changes the source must also fix or drop the copy. Missing one path yields stale data that is hard to reproduce.

| Method | How | Fits | Risk |
|---|---|---|---|
| **TTL** | Entry expires after N seconds | Everything, as a safety net | Stale up to N; sets a hard bound on error |
| **Explicit delete on write** | Write path deletes (or updates) the key | Entity caches with few write paths | A missed write path; delete-vs-fill race (a reader refills old data after your delete). Prefer delete over update; keep TTL as backstop |
| **Versioned keys** | Key includes a version or content hash (`user:42:v7`, `app.3f9a.js`) | Static assets, config, derived data | Old versions linger until evicted; you must store or look up the current version |
| **Event-driven** | Change events (CDC, message bus) trigger deletes | Many writers, multiple caches, other services own the data | Lost or reordered events; lag; still keep a TTL |

Practice: pick TTL from "how stale can the user tolerate" (stated in requirements), add explicit delete on every write path you can find (grep for all writers, including admin tools, jobs and migrations), and still set a TTL. Prefer short TTL plus jitter over a clever scheme you cannot test.

## 5. Eviction policies

Eviction decides what to drop when the cache is full. It removes only the cached copy; the source is unaffected. Do not confuse it with expiry (TTL) or invalidation.

| Policy | Evicts | Fits | Weakness |
|---|---|---|---|
| **LRU** | Longest unused | General default; recency predicts reuse (web objects, DB pages, metadata) | A big one-time scan flushes hot items; needs ordering bookkeeping |
| **LFU** | Fewest accesses | Stable long-term popularity (catalog, query results) | Slow to adapt when popularity shifts; new items can be evicted before they build a count; counters cost memory |
| **FIFO** | Oldest inserted | Cheap and predictable; when age matters more than use | Ignores usage, can evict hot items |
| **MRU** | Most recently used | Sequential scans/looping reads where the item just used will not return soon | Bad for normal workloads |
| **Random** | A random entry | Very low overhead, non-critical caches | Can drop hot items; no adaptation |
| **TTL-based** | Entries past expiry | Data with a natural freshness window | Does not bound memory by itself; pair with another policy |
| **Others** (LRU-K, ARC, 2Q, TinyLFU/W-TinyLFU) | Hybrid recency/frequency | Scan-resistant, better hit rate | More complex; usually come inside a library |

The source page lists only LRU, LFU, FIFO and random (and its worked LRU example has the order wrong). MRU, TTL-based and the hybrids here are standard additions.

In code: pick the policy your cache already offers (Redis `maxmemory-policy` such as `allkeys-lru`/`allkeys-lfu`, or `volatile-*` to evict only keys with a TTL). Set a memory limit, otherwise the cache grows until the host dies. Watch the eviction rate: high evictions with a low hit rate mean the cache is too small or the keys are too varied.

## 6. Distributed caches

A distributed cache spreads entries over several nodes so capacity and throughput scale by adding nodes, and the data is shared by all app instances.

- **Partitioning**: node = f(hash(key)). Plain `hash % N` remaps almost every key when N changes, causing a miss storm. **Consistent hashing** (with virtual nodes) moves only about 1/N of keys on a membership change. See `load-balancing.md`. Redis Cluster uses fixed hash slots, similar in effect.
- **Replication**: copies on other nodes give availability and read capacity. Async replication is fast but a failover can lose recent writes or serve stale reads; sync is safer but slower. For a cache, async is usually fine because the DB is the source of truth.
- **Consistency**: replicas can briefly disagree, and cache vs DB can disagree longer. Treat the cache as eventually consistent; never use it as the system of record unless you chose a durable store on purpose. See `availability-and-consistency.md`.
- **Failure behavior**: a node loss drops its keys (cold misses go to the DB) unless replicated. Clients need timeouts, a fallback to the source, and a circuit breaker so a slow cache does not become the outage. A flush or restart is a cold start (section 8).
- **Operations**: monitor hit rate, latency, evictions, memory, node health, replication lag; rebalance when adding nodes.

### Design outline (distributed cache)

1. **Requirements.** Functional: get/set/delete with TTL, eviction, add/remove nodes, replication. Non-functional: p99 < ~5 ms in-DC, scale horizontally, survive one node failure, stated staleness. Out of scope: durability, complex queries.
2. **Components.** Client library (routes by key hash) -> cache nodes (in-memory store, e.g. Redis/Memcached, each owning a key range) -> cluster manager (membership, failure detection, rebalancing) -> source DB (read on miss) -> monitoring.
3. **API.** `GET key`, `SET key value ttl`, `DELETE key`; admin: add/remove node, rebalance, metrics, node health. Define miss behavior (a clear "not found", not an error).
4. **Sizing arithmetic** (example): 10k reads/s + 1k writes/s; 1 KB entries x 1M entries = 1 GB raw. Add per-entry overhead (keys, metadata, roughly 50-100% for small values) and replication (x2 with one replica): about 3-4 GB. With 10 GB nodes the data fits in one node, so node count here is set by **throughput and failure tolerance**, not capacity: 3 nodes (one failing still leaves capacity). Bandwidth: 10k x 1 KB = ~10 MB/s reads. Always check the hot-key share: one key at 20% of traffic caps at one node's throughput.
5. **Deep dives**: hashing and rebalancing, hot-key handling, stampede protection, replica failover. Trace each to a requirement.

The source's design page mixes a persistent DB table into the cache design and never explains the hash ring; treat the outline above as the standard form.

## 7. Edge caching, CDN vs edge server

**Edge caching** serves content from servers near users. A request is routed (DNS, anycast, latency-based) to a nearby edge; a hit returns without touching the origin; a miss fetches from origin (or a mid-tier cache), serves it and stores it if headers allow. Benefits: lower latency, less origin load and egress. Costs: staleness, slow global purges, limited edge storage (so eviction applies), misses still pay origin latency.

Engineer it with: `Cache-Control` (`max-age`, `s-maxage` for shared caches, `private` for per-user content, `no-store` for sensitive data), validators (`ETag`/`Last-Modified` with conditional requests), `Vary` only on headers that really change the response, hashed filenames for assets (cache forever, never purge), and purge APIs or surrogate-key tags for the rest. See `networking.md` for CDN and DNS basics.

| | CDN | Edge server |
|---|---|---|
| What it is | A network of many edge locations (PoPs) | One server at one edge location or near a device |
| Scope | Global, managed delivery system | Single node; can be part of a CDN or a private setup |
| Main job | Fast delivery of static/cacheable content | Caching, reverse proxy, security filtering, local compute |
| Content | Mostly static, some dynamic and edge functions | Static or dynamic, per its role |
| Typical uses | Websites, video, downloads, cacheable APIs | IoT preprocessing, local compute, a CDN cache node |

A CDN edge node is itself an edge server, so the difference is scope and purpose, not kind. (The source article calls a PoP the component that routes traffic; routing is really done by DNS/anycast.)

## 8. Cold vs warm cache

- **Cold**: holds little of the working set (after start, deploy, flush, failover, new node). Hit rate is low, latency rises and the backend takes the full load.
- **Warm**: holds the hot set; most reads hit.
- **Warming** shortens the cold period: preload known-hot keys (top N from logs or analytics), prefetch related data, copy hot entries from a warm replica or peer, replay recent traffic, or load critical keys before shifting traffic to a new instance.

Trade-offs: warming loads data that may never be read, adds backend load of its own (rate-limit it), and bad predictions waste memory. It improves odds, it does not guarantee fast first requests. Design rule: size the backend to survive a fully cold cache, or ramp traffic gradually after a deploy or restart. Avoid flushing everything at once; expire or version instead.

## 9. Failure modes and mitigations

| Problem | What happens | Mitigations |
|---|---|---|
| **Stampede / thundering herd** | A hot key expires and many requests hit the DB at once | Per-key lock or request coalescing (single flight); refresh-ahead; serve stale while one request refreshes; TTL jitter |
| **Penetration** | Requests for keys that do not exist always miss and hit the DB (often an attack) | Cache negative results with a short TTL; Bloom filter of valid keys; validate input; rate limit |
| **Avalanche** | Many keys expire together, or the cache dies, and the DB is flooded | Randomize TTLs; staggered warming; replicas; circuit breaker and load shedding to protect the DB |
| **Hot keys** | One key's traffic overloads a single node | Local in-process copy of the hot key; replicate or split the key (`key#1..k`); CDN for public data |
| **Stale data** | Source changed, cache did not | Bounded TTL; delete on every write path; versioned keys; events; show or accept the staleness window |
| **Caching errors** | A failure, timeout or empty fallback gets cached and served for the full TTL | Cache only successful, validated results; cache failures with a very short TTL if at all; never cache a partial result |
| **Cache down** | Reads fail or latency spikes | Timeout, fall back to the source, circuit breaker, DB sized for the fallback |
| **Data leak** | Private data served to another user | Scope the key by user/tenant; see checklist |

## 10. Checklist for adding a cache in code

1. **Measure first**: baseline p50/p95/p99 and the DB/downstream load. Confirm the path is read-heavy and slow, and state the target ("p95 from 400 to 80 ms").
2. **Key design**: deterministic and namespaced: `app:entity:id:version`. Include every input that changes the result (locale, filters, API version, format). **Include user or tenant id for anything user-specific or access-controlled**, so one user's data is never served to another. Never cache private responses at shared layers (CDN, proxy) without `private`/`no-store` or a key that includes identity. Keep keys bounded in length; hash large inputs.
3. **TTL**: derived from the tolerated staleness, with jitter; shorter for volatile data. No TTL-less entries unless versioned.
4. **Invalidation on every write path**: list each place that writes the data (API handlers, jobs, admin scripts, migrations, other services) and handle each. Delete rather than update; keep the TTL as backstop.
5. **Cache down**: set client timeouts (tens of ms, not seconds), fall back to the source, add a circuit breaker, and decide what happens on write when the cache is unreachable (delete fails: retry or rely on TTL). Confirm the source can take the full load.
6. **Stampede and penetration**: single-flight on hot keys, negative caching, TTL jitter.
7. **Serialization**: version the cached format so a deploy that changes the shape does not read old entries incorrectly; handle deserialize errors as a miss.
8. **Memory**: set a size limit and eviction policy; estimate entries x size x replicas.
9. **Metrics**: hit rate, miss rate, latency per outcome, evictions, memory, errors, and backend load. Alert on a sudden hit-rate drop. Log keys carefully (no secrets or PII).
10. **Tests**: hit path, miss path, expiry, invalidation after each write path, cache-unavailable fallback, two users/tenants cannot read each other's entry, and a stampede test (N concurrent misses cause one load). Run with the cache disabled too, to prove correctness does not depend on it.
11. **Docs**: record the staleness window, key format and invalidation rules in the code or design doc, so the next change does not miss a write path.
