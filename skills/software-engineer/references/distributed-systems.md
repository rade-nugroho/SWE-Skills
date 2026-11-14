# Distributed systems

Use this when a change crosses a process or network boundary: a new service call, a queue consumer, replicated or sharded data, leader election, locks, cross-service tracing, or service-to-service auth. If everything runs in one process against one database, you can skip it.

## Contents
1. What "distributed" costs
2. Fallacies and what each means for code
3. Design issues → what to decide
4. Time and ordering
5. Consensus
6. Quorums and split-brain
7. Distributed tracing
8. Secure communication between nodes
9. Design-review checklist

Related: `fault-tolerance.md` (timeouts, retries, breakers), `availability-and-consistency.md` (CAP, consistency models, quorum reads/writes), `database-design.md` (replication), `event-driven.md`, `networking.md`, `load-balancing.md`, `security.md`.

## 1. What "distributed" costs

A distributed system is independent machines cooperating over a network so users see one service. Splitting buys capacity, parallelism, redundancy, and locality to users. It also adds four costs a single process doesn't have:

| Cost | What it means | Consequence for code |
|---|---|---|
| Partial failure | Some parts fail while others keep running | Every remote call can fail, hang, or succeed without you learning it. Design the "unknown outcome" path. |
| Unreliable network | Messages are delayed, dropped, duplicated, reordered | Timeouts on every call; retries need idempotency; consumers tolerate duplicates and reordering. |
| No shared clock | Each machine's clock drifts and jumps | Never order events across machines by wall-clock time (section 4). |
| Concurrency | Nodes act at once, with no shared memory or lock | Use a store-level primitive (transaction, compare-and-set, lease), not an in-process mutex. |

A slow node and a dead node look the same from outside. A timeout tells you "no answer yet", not "it didn't happen".

## 2. Fallacies and what each means for code

The classic false assumptions. Each one is a bug waiting in code that makes it.

| Assumption | Reality | Do this |
|---|---|---|
| The network is reliable | Calls fail and vanish | Timeout + bounded retry + defined failure behavior |
| Latency is zero | A remote call is ~1000x a local one | No remote calls in tight loops; batch; avoid N+1 across services |
| Bandwidth is infinite | Payloads cost time and money | Paginate, compress, send IDs not whole objects |
| The network is secure | Traffic can be read or altered | TLS everywhere, authenticate callers (section 8) |
| Topology doesn't change | Instances come and go, IPs change | Service discovery or DNS with re-resolution; no hard-coded addresses |
| There is one administrator | Many teams, versions, policies | Versioned, backward-compatible contracts; expect old clients |
| Transport cost is zero | Serialization, connections, egress all cost | Reuse connections; measure payload size |
| The network is homogeneous | Mixed languages, runtimes, protocol versions | Stick to open formats; tolerate unknown fields |

## 3. Design issues → what to decide

| Issue | What to decide in the design |
|---|---|
| Transparency: access | Callers use the same interface for local and remote? If remote, make failure and latency visible in the signature (async, error result), not hidden. |
| Transparency: location | How clients find a resource (discovery, naming); what happens when it moves. |
| Transparency: replication | Which copy a client reads; how stale it may be; who is told about lag. |
| Transparency: failure, concurrency (also common in the literature) | Whether callers see retries or conflicts, or the system absorbs them. |
| Openness | Public interfaces and wire formats; versioning and compatibility rules; who can add a new node or client. |
| Scalability | Which dimension grows (users, data, services); the bottleneck; whether state is partitioned or shared; avoid central coordination on the hot path. |
| Heterogeneity | Languages, OSes, hardware, protocol versions in play; the common contract (IDL, schema, HTTP/JSON, gRPC). |
| Security | Trust boundaries; identity of each service; encryption in transit; authorization per call (section 8). |
| Failure handling | How failures are detected (heartbeats, timeouts); what is retried, failed fast, or degraded; recovery without losing committed data. |
| Concurrency | Who may write a resource at once; the conflict rule (lock, version check, last-writer-wins, merge); where the lock lives. |
| Quality of service | Latency, throughput, availability targets with numbers; deadlines for real-time paths; behavior under overload (shed, queue, back-pressure). |

Name the choice and the reason in the design doc, as `system-design.md` asks. An unstated default (for example "last write wins") is still a decision.

## 4. Time and ordering

- **Physical clocks** (wall time, NTP-synced) are close but not equal across machines. They drift, can step backward on correction, and differ by milliseconds or more. Fine for logs, TTLs, display. Wrong for deciding which of two writes happened first.
- **Logical clocks** track causality instead of time.
  - Lamport clock: a counter per node, incremented on each event and set to max(own, received)+1 on receive. If A happened-before B, then A's stamp < B's; the reverse does not hold.
  - Vector clock: a counter per node carried in each message; compare two vectors to tell "before", "after", or "concurrent". Costs space proportional to node count.
- Why wall-clock timestamps can't order events: with 5 ms of skew, a write at node B can get an earlier timestamp than a causally earlier write at node A, and "last write wins" then silently drops the newer one.

What to do in code:
- Order within one entity by a version number or sequence from the single owner of that entity (DB row version, partition offset, leader-assigned index), not by `now()`.
- Use compare-and-set on a version for concurrent updates; surface conflicts instead of overwriting.
- Use monotonic clocks (not wall time) for measuring durations and timeouts.
- If you must use timestamps for expiry (leases, tokens), allow a margin for skew and never rely on exact cross-machine equality.
- A lock with a timeout can expire while its holder is paused; pass a fencing token (increasing number) with each write and have the storage reject stale tokens.

## 5. Consensus

Consensus lets several nodes agree on one value even when some fail. You need it for: leader election, a replicated log or state machine, cluster configuration and membership, distributed locks and leases, and deciding commit order.

| Algorithm | Fault model | Nodes for f faults | Style | Where you meet it |
|---|---|---|---|---|
| Paxos (Multi-Paxos) | Crash | 2f+1 (majority) | Quorum, numbered proposals; prepare/accept phases | Google Chubby and Spanner-style systems; many internal stores |
| Raft | Crash | 2f+1 (majority) | Elected leader replicates a log; re-election on leader loss | etcd (Kubernetes), Consul, Kafka KRaft, CockroachDB |
| ZAB | Crash | 2f+1 (majority) | Leader-based atomic broadcast | ZooKeeper |
| PBFT | Byzantine | 3f+1 | Primary plus replicas; pre-prepare, prepare, commit | Permissioned BFT ledgers; BFT research and variants |
| Proof of work | Byzantine, open membership | Honest majority of compute (not a node count) | Miners race; longest chain wins; finality is probabilistic | Bitcoin-style chains |
| Proof of stake | Byzantine, open membership | Typically honest majority of stake; finality gadgets often assume under 1/3 faulty | Validators chosen by stake | Ethereum-style chains |

Notes:
- 2f+1 for crash faults: a majority (f+1) must still be alive, so 3 nodes tolerate 1, 5 tolerate 2, 7 tolerate 3. Even sizes add cost with no extra tolerance (4 tolerates 1, same as 3).
- 3f+1 for Byzantine faults: you need enough honest replicas to outvote liars and still reach a quorum, so 4 nodes tolerate 1 and 7 tolerate 2.
- Crash fault tolerance assumes nodes fail by stopping, not by lying. If a node can be compromised or buggy in arbitrary ways, you need BFT, which is slower and more complex.
- The source page covers only Raft, Paxos, and PBFT. ZAB, proof of work, and proof of stake rows, and the node-count formulas, come from standard references.
- More nodes is not faster: every commit waits for a quorum, so latency follows the slowest member of the quorum. Typical clusters are 3 or 5 nodes.

Practical rule: use an existing coordination service or library, and do not write consensus yourself.

| Need | Reach for |
|---|---|
| Config, service discovery, leader election, locks | etcd, Consul, or ZooKeeper (or the managed one your platform provides) |
| Replicated log or state machine inside your app | A tested Raft library (for example hashicorp/raft, etcd raft, Apache Ratis) |
| Durable ordered events | Kafka (KRaft for its own metadata) or a managed log |
| Unique-owner semantics on one resource | A database row with a version or unique constraint, or a lease in a coordination service |

Hand-rolled leader election by "lowest ID wins" or "whoever writes a key first" breaks under partitions and pauses. If a design calls for consensus, say which service or library provides it and what its failure mode is.

## 6. Quorums and split-brain

- A quorum is a majority of a fixed membership. Any two majorities overlap in at least one node, so two quorums can't decide conflicting things.
- For N replicas with write quorum W and read quorum R, requiring R + W > N makes every read overlap the latest write. Details and consistency trade-offs: `availability-and-consistency.md`.
- Split-brain: a partition leaves two groups each believing they are in charge, both accept writes, and the data diverges. Majority quorum prevents it, since only the side with a majority can proceed; the minority side must stop writing (it loses availability, which is the CAP trade).
- Two-node clusters can't form a majority after one failure. Use 3 nodes, or add a tiebreaker (witness) node.
- A deposed leader may not know it was replaced. Guard writes with the leader's term or epoch, and fence stale leaders (section 4).
- Config changes to membership are a consensus decision too; use the library's reconfiguration, not manual edits to member lists.

## 7. Distributed tracing

Logs show what one service did; metrics show aggregate health; a **trace** shows one request's path across services. Use the three together: a metric alert finds the problem, a trace finds the slow or failing hop, logs from that span explain why.

| Term | Meaning |
|---|---|
| Trace | All work for one request, sharing a trace ID |
| Span | One operation inside a trace: name, start/end, attributes, status, parent span ID |
| Context propagation | Passing trace ID and parent span ID to the next hop; if any hop drops it, the trace splits in two |
| W3C `traceparent` | Standard header: version, trace ID, parent span ID, flags. Format `00-<32 hex>-<16 hex>-<2 hex>` |
| Sampling | Keep only some traces. Head-based: decide at the start, cheap, may miss rare errors. Tail-based: decide after the trace completes (keep errors and slow ones), needs buffering in a collector. |

Tooling: OpenTelemetry (OTel) is the vendor-neutral API, SDKs, and collector for producing and exporting telemetry. Backends that store and display traces include Jaeger, Zipkin, Grafana Tempo, and cloud services such as AWS X-Ray. Code against OTel and swap the backend by config.

When you touch a service call, add or check:
- [ ] Trace context is extracted on inbound requests and injected on outbound ones (HTTP headers, gRPC metadata). Prefer the framework's OTel instrumentation over hand-written header code.
- [ ] Spans are named for the operation, low cardinality: `GET /orders/{id}`, `orders.reserve_stock`, not a URL with the ID filled in.
- [ ] Failures are recorded on the span: record the exception and set error status.
- [ ] Useful attributes are added (tenant, order type, retry count), and none contain secrets or personal data.
- [ ] For queues and events, put the trace context (and a correlation ID) in message headers; the consumer starts a span linked to the producer's, since the producer span may have ended long ago.
- [ ] Background and scheduled jobs start a new trace with a clear root span name.
- [ ] Log lines carry the trace ID and span ID so logs and traces join.
- [ ] A request ID returned to the client or shown in error pages matches the trace ID, so support can look it up.
- [ ] Sampling rate is a deliberate choice; storage cost grows with traffic.

## 8. Secure communication between nodes

Threats on the wire: eavesdropping, impersonating a service, tampering with messages, and replaying captured ones. Don't treat "inside the private network" as trusted. A zero-trust stance means every call is authenticated and authorized on its own merits.

| Concern | Typical mechanism |
|---|---|
| Confidentiality and integrity in transit | TLS (1.3 preferred; 1.2 only with a strong configuration); disable old protocols and weak ciphers |
| Both sides prove who they are | Mutual TLS (mTLS) with per-service certificates, often issued through a service mesh or SPIFFE-style identities |
| Who may call what | Authenticate the caller, then authorize per call (roles or scopes; OAuth 2.0 tokens, signed JWTs); least privilege per service |
| Asynchronous messages that cross brokers | Message-level signing or encryption, since transport TLS ends at the broker; include a message ID or timestamp to resist replay |
| Keys and certificates | Issued by a CA, stored in a secrets manager (never in source), short-lived, rotated automatically, with expiry monitored |

For code changes: use the platform's TLS and verify certificates (never disable verification to "make it work"), pass the caller's identity down instead of trusting a header any client could set, and check key or certificate expiry as an operational risk. Depth (threat modeling, secret handling, authn/authz design): `security.md`.

## 9. Design-review checklist for distributed changes

- [ ] Timeouts: every remote call has one, shorter than the caller's own deadline; deadlines propagate down the chain.
- [ ] Retries: transient errors only, bounded, backoff with jitter, and no retry stacking across layers (a retry at each of 3 layers is 27 attempts).
- [ ] Idempotency: retried writes and consumed messages are safe to apply twice (idempotency key, unique constraint, or version check).
- [ ] Ordering: does the code assume messages arrive in order or once? If so, where is order guaranteed (one partition, one owner)?
- [ ] Clocks: no cross-machine ordering by wall-clock time; expiry has skew margin; durations use monotonic time.
- [ ] Partial failure: for a call that times out, the code knows the outcome may be "done", and a reconciliation or status check exists.
- [ ] Multi-service updates: saga or compensation, or an outbox pattern, not a hoped-for "both succeed".
- [ ] Coordination: any lock, leader, or unique-owner need uses an existing service or DB primitive, with fencing; membership is odd-sized (3 or 5).
- [ ] Failure behavior is defined for each dependency being down: fail fast, fallback, or degrade.
- [ ] Contracts: wire formats are versioned and tolerate old and new peers during rollout.
- [ ] Security: TLS or mTLS on the path; caller identity checked; no secrets in traces or logs.
- [ ] Observability: trace context propagated, spans named, errors recorded, correlation ID through queues; metrics for rate, errors, latency per dependency.
- [ ] Tests: simulate timeout, duplicate delivery, reordering, and a dependency outage for the new path.
