# API gateways, message queues, and rate limiting

Use this when a change adds a shared client entry point, moves work off the request path, or caps caller traffic. `system-design.md` has the one-line entries; this covers how to decide and what to check.

## Contents
1. API gateway
2. Message queues
3. Rate limiting
4. Token-bucket sketch (Python)
5. Combined checklist

Related: `event-driven.md` (sagas, outbox), `load-balancing.md`, `networking.md` (proxies), `fault-tolerance.md`, `security.md`, `architecture-styles.md`.

## 1. API gateway

A gateway is one front door between clients and your backend services. It applies the policies every request needs, then forwards the request. Clients see one address; the service split stays hidden.

### What it does

| Job | What to check in the design |
|---|---|
| Routing | Route rules (path, host, method, header) live in versioned config, not hand-edited on a box |
| Authentication | Gateway verifies the token (JWT, API key, OAuth); services still check authorization for their own data (see `security.md`) |
| Rate limiting | Per key limits at the edge (section 3) |
| TLS termination | Decide whether gateway-to-service traffic is re-encrypted; plain HTTP inside the network is a conscious choice |
| Transformation | Header injection, REST to gRPC; keep it mechanical |
| Aggregation | One client call fans out to several services; set a timeout per branch and decide what a partial result looks like |
| Caching | Only responses safe to share; cache key includes user or locale if the answer varies |
| Observability | Request ID created or forwarded here, access logs, latency and error metrics per route |

### Gateway vs load balancer vs reverse proxy

These overlap, and one product often plays several roles; pick by the job needed.

| | Main job | Understands | Typical extras | Example products |
|---|---|---|---|---|
| Load balancer | Spread traffic across identical instances | Connections (L4) or HTTP (L7) | Health checks, TLS | HAProxy, cloud LBs |
| Reverse proxy | Sit in front of servers, hide them, forward requests | HTTP | Caching, compression, TLS, static files | Nginx, Envoy |
| API gateway | Apply API policy per route and per client | API concepts: keys, plans, routes, schemas | Auth, rate limits, transformation, aggregation, developer portal | Kong, AWS API Gateway, Apigee |

A gateway is usually a reverse proxy plus API-aware policy. See `load-balancing.md`, `networking.md`.

### Backend for frontend (BFF)

Instead of one gateway for everyone, run one thin gateway per client type (web, mobile, partner). Each shapes responses for its client: mobile gets small payloads and fewer round trips, partners get a stable versioned contract. Use it when client needs diverge enough that one gateway fills up with `if client == mobile`. Each BFF belongs to the team that owns that client.

### Risks

- **Single point of failure.** Run two or more instances across zones; test that losing one is invisible.
- **Added latency.** Measure p95 through the gateway vs direct; keep per-request auth lookups cached or local.
- **Business logic creeping in.** The gateway should not know about orders or pricing. Test: could the rule change without a domain expert? If not, it belongs in a service. Mechanical rules (auth, limits, routing) stay.
- **Shared blast radius.** A bad route config breaks every API; roll out gradually, default deny, review route changes like code.

### When a small system does not need one

Skip it with one backend (or a modular monolith), few client types, and a framework or reverse proxy that already covers TLS, auth middleware, and a simple limit; a gateway would add a failure point with nothing to centralize. Reach for one when several services share auth, limits, and routing, partners need keys and plans, or clients should not know the service layout.

## 2. Message queues

A queue buffers messages between a producer and a consumer that runs later at its own pace.

### When to use one

| Use | Why | Example |
|---|---|---|
| Async work | The caller does not need the result now | Send email, resize image, generate report |
| Smoothing spikes | Consumers take work at a steady rate; the queue absorbs the peak | Flash-sale orders |
| Decoupling | Producer does not care if the consumer is slow or down | Order service and invoicing |
| Retries | Failed work is redelivered without the caller retrying | Webhook delivery |
| Fan-out | Several systems react to one event | Order created: stock, email, analytics |

Skip it when the caller needs the answer to continue (call directly, with a timeout), when volume is tiny and a DB row plus a worker loop suffices, or when consumers cannot be made idempotent. A queue is one more thing to run and debug: a request is no longer one stack trace.

### Three shapes

| | Point-to-point queue | Publish/subscribe | Log / stream |
|---|---|---|---|
| Delivery | Each message goes to one of many competing consumers | Each subscriber gets its own copy | Consumers read a durable ordered log at their own offset |
| After consumption | Message removed on ack | Removed per subscription | Stays until retention expires; replay is possible |
| Best for | Work distribution, job queues | Event notification to many parties | Event history, analytics, rebuilding state, high throughput |
| Ordering | Weak by default | Weak by default | Strong within a partition |
| Example products | SQS, RabbitMQ queues, Sidekiq | SNS, Google Pub/Sub, RabbitMQ exchanges | Kafka, Kinesis, Redpanda |

Many products cover more than one shape; choose by the semantics you need. Event patterns and sagas: `event-driven.md`.

### Behavior you must design for

- **Delivery guarantee.** Assume at-least-once: a message can arrive twice (consumer crashed after working but before ack). At-most-once loses messages on failure. "Exactly once" is only achievable end to end by combining at-least-once delivery with an idempotent consumer (or transactional features inside one system).
- **Acknowledgement.** Ack only after the work and its side effects are done. Ack-on-receive turns a crash into silent data loss.
- **Visibility timeout / lease.** While a consumer holds a message, it is hidden from others. Set the timeout longer than the p99 processing time; extend it for long jobs. Too short means duplicate processing, too long means slow recovery from a dead consumer.
- **Ordering.** Parallel consumers and retries break order. If order matters per entity (one account, one order), use a FIFO queue with a group ID or a log with a partition key, and accept that throughput is per partition. If it matters globally, one consumer, and say so. Better still: make handlers tolerate out-of-order events (version numbers, "ignore if older").
- **Poison messages and dead-letter queue.** After N failed attempts, move the message to a DLQ instead of retrying forever and blocking the line. Alert on DLQ depth above zero, keep the failure reason, and have a tested way to replay.
- **Backpressure.** An unbounded queue hides overload until memory or disk runs out. Bound it, and decide what a full queue does to producers: block, drop, or return an error such as HTTP 503 with `Retry-After`. Producers that retry should back off.
- **Idempotent consumers.** Dedupe on a message or business ID (unique constraint, conditional write) so a repeat has no extra effect.
- **Producer atomicity.** "Write DB then publish" can lose the event on crash; use the outbox (`event-driven.md`).

### Sizing and monitoring

Workers needed is roughly arrival rate times average processing seconds, plus headroom for peaks and retries. In a log, partitions cap parallelism: extra consumers sit idle.

| Signal | Means | Alert when |
|---|---|---|
| Queue depth | Backlog | Grows steadily, or passes a size that implies minutes of lag |
| Consumer lag (logs) | Offsets behind head | Rising for several minutes |
| Age of oldest message | How stale work is; best user-facing signal | Passes the latency you promised |
| DLQ depth | Messages that failed for good | Greater than zero |

### Review checklist: producers and consumers

Producer:
- [ ] Message has ID, type, version, timestamp; no secrets; publish atomic with the state change (outbox) or loss accepted
- [ ] Partition or group key set when order per entity matters

Consumer:
- [ ] Idempotent, tested by delivering twice
- [ ] Ack after success only; failures retried, then dead-lettered; visibility timeout above p99
- [ ] Concurrency limit protects downstream services and the DB

## 3. Rate limiting

Rate limiting caps how many requests a caller may make in a period. Reasons: protect capacity, stop abuse and credential stuffing, share capacity fairly, control cost of paid downstream calls, and enforce plans. It does not replace capacity planning and only partly helps against large distributed floods.

### Where and by what key

| Layer | Pros | Cons |
|---|---|---|
| Client (SDK, app) | Politeness, saves wasted calls | Can be bypassed; never the only control |
| Edge / gateway | Rejects early, cheap, one policy for everything | Coarse: knows caller and route, not business cost |
| Service | Knows real cost (an expensive search vs a cheap read) | Each service reimplements it unless shared |

Layer them: coarse at the gateway, cost-aware in services for expensive operations.

| Key | Use for | Watch out for |
|---|---|---|
| Per user / account | Logged-in APIs | Needs auth first; anonymous traffic needs another key |
| Per IP | Anonymous endpoints, login | Shared NAT or office IPs punish innocents; attackers rotate IPs; check which header holds the real client IP and that it cannot be spoofed |
| Per API key | Public or partner APIs | Leaked keys; limits per plan |
| Per tenant | Multi-tenant SaaS | One noisy tenant should not starve others; combine with per-user inside the tenant |

Often combine keys, with stricter limits on login and password reset.

### Algorithms

| Algorithm | How it works | Burst behavior | Memory per key | Pick when |
|---|---|---|---|---|
| Token bucket | Bucket refills at a steady rate up to a capacity; each request takes a token | Allows bursts up to capacity, then the refill rate | Two numbers (tokens, last time) | Default for APIs: bursts are fine, long-run average is capped |
| Leaky bucket | Requests join a bounded queue drained at a constant rate; full queue drops | Smooths output; bursts become delay or drops | Queue length or counter | A downstream needs a steady rate |
| Fixed window counter | Counter per time window (for example per minute); reset at the boundary | Up to 2x the limit across a boundary (end of one window plus start of next) | One counter | Simple, coarse quotas where the boundary spike is acceptable |
| Sliding window log | Store a timestamp per accepted request; count those inside the last window | Exact; no boundary spike | One entry per request, grows with the limit | Low limits where precision matters (login attempts) |
| Sliding window counter | Keep counters for the current and previous window; estimate the rolling count as current plus previous weighted by the overlap fraction | Close to exact, small error; no big boundary spike | Two counters | High-volume APIs that want smooth limits cheaply |

Many "leaky bucket" code samples only reject when full and never queue; decide whether you want delay or rejection.

### Distributed rate limiting

With several app instances, per-instance counters allow N times the limit. Options:

- **Shared store (Redis).** All instances check one counter per key. Use atomic operations: `INCR` plus `EXPIRE` for fixed windows, or a Lua script / transaction for token bucket and sliding windows. A read-then-write from app code races: two instances read the same count and both allow the request.
- **Local approximation.** Each instance gets limit divided by instance count, or syncs counts periodically. Cheap, but uneven load makes it inaccurate: fine for protecting capacity, weak for paid quotas.
- **Decide failure mode.** If the store is down, fail open (allow, risk overload) or fail closed (reject, risk outage). Choose per endpoint: open for general reads, closed for login and costly operations. Add a short timeout on the store call so the limiter does not become the slowest part.
- Give keys a TTL so memory does not grow forever.

### Responding to the client

- Reject with **HTTP 429 Too Many Requests**, not 403 or 500, and a body saying which limit was hit.
- Send **`Retry-After`** (seconds or a date) so clients know when to return.
- Send limit headers so clients can pace themselves: commonly `X-RateLimit-Limit`, `-Remaining`, `-Reset` (an IETF draft proposes `RateLimit-*`). Pick one and document it.

What a client should do on 429 or 503:
1. Stop sending; wait at least `Retry-After`.
2. Without that header, back off exponentially with jitter and a retry cap (`fault-tolerance.md`).
3. Retry only idempotent requests or ones with an idempotency key; pace from the quota headers.

## 4. Token-bucket sketch (Python)

Single process, clock injected so tests never sleep. For several instances, put the same arithmetic in a Redis Lua script so refill and spend are one atomic step; for threads, lock `allow`.

```python
import time


class TokenBucket:
    def __init__(self, capacity, refill_per_sec, clock=time.monotonic):
        self.capacity = capacity
        self.rate = refill_per_sec
        self.clock = clock
        self.tokens = float(capacity)     # start full: allows an initial burst
        self.last = clock()

    def _refill(self):
        now = self.clock()
        elapsed = max(0.0, now - self.last)   # guard against a backwards clock
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last = now

    def allow(self, cost=1):
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def retry_after(self, cost=1):
        """Seconds until `cost` tokens exist; feed this to Retry-After."""
        self._refill()
        return max(0.0, cost - self.tokens) / self.rate


class FakeClock:
    t = 0.0

    def __call__(self):
        return self.t


clock = FakeClock()
b = TokenBucket(capacity=5, refill_per_sec=1, clock=clock)
assert [b.allow() for _ in range(6)] == [True] * 5 + [False]   # burst, then empty
assert b.retry_after() == 1.0
clock.t += 2
assert b.allow() and b.allow() and not b.allow()               # 2 s refills 2 tokens
clock.t += 1000
assert b.allow() and b.tokens <= 5                             # capped at capacity
```

Across machines, use the store's clock (Redis `TIME`), not each server's wall clock.

## 5. Combined checklist

- [ ] Gateway justified by several services or clients; two or more instances; per-route timeouts; only mechanical rules, no domain logic
- [ ] Queue used because the caller does not need the result now; at-least-once assumed; consumers idempotent; ack after success
- [ ] Retry limit, DLQ with alert, and a replay path; visibility timeout above p99; order handled by key or tolerated
- [ ] Queues bounded with defined full behavior; alerts on depth, oldest age, lag
- [ ] Rate-limit key and layer chosen on purpose; stricter on login and costly routes; algorithm matches the burst need
- [ ] Shared limiter state is atomic; store-down behavior (fail open or closed) decided
- [ ] 429 with `Retry-After` and documented limit headers; clients back off with jitter
- [ ] Limiter tested with a fake clock at the limit, over it, and after refill
