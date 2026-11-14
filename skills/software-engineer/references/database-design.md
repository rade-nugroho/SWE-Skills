# Database design and schema changes

Use this when a task adds or changes tables/collections, picks a datastore, scales or replicates data, tunes queries, or moves data.

## Contents
1. Lifecycle
2. Conceptual, logical and physical design
3. Choosing a database type
4. SQL vs NoSQL decision table
5. File vs database storage; block, object, file storage
6. Normalization (1NF to BCNF) and denormalization
7. SQL query optimization checklist
8. Replication
9. Partitioning and sharding
10. Redis
11. Changing an existing schema (migrations)
12. Data conversion and loading
13. Testing
14. Checklist

## 1. Lifecycle

planning → requirements (entities, access patterns, volumes) → **conceptual** → **logical** → **physical** design (with DBMS selection alongside, and application design in parallel) → prototype and loop back if it doesn't fit → implement → **data conversion & loading** → test → operate & maintain.

## 2. Conceptual, logical, physical design

**Conceptual**
- Entities, their attributes, and relationships (1:1, 1:N, M:N) — an ER diagram in Mermaid (`erDiagram`) is enough.
- Independent of any database product.

**Logical**
- Map to the chosen model (relational tables / documents / key-value).
- Relational: normalize to 3NF by default; each fact stored once. Denormalize later only for a measured read-path need (section 6).
- Choose primary keys (surrogate vs natural), foreign keys, unique constraints, NOT NULL, check constraints. Constraints in the DB are the last line of defense against bad data — prefer them over app-only checks.
- Document/KV: design from the **access patterns** first (what queries, by which key), then shape the documents to answer them.

**Physical**
- Indexes for the real query patterns (WHERE / JOIN / ORDER BY columns); every index slows writes, so justify each.
- Data types and sizes, partitioning/sharding key, retention/TTL, storage engine settings.
- DBMS selection: sections 3–5. Building blocks overview is in `system-design.md`.

## 3. Choosing a database type

Start from the access patterns and the guarantees the data needs, not from the product you know. Most systems end up polyglot: one system of record plus specialized stores derived from it.

| Type | Use when | Example products | Watch out for |
|---|---|---|---|
| Relational (RDBMS) | Structured data, relations, multi-row transactions, ad-hoc queries and reporting | PostgreSQL, MySQL, SQL Server, Oracle | Vertical limits; sharding is manual work |
| Key-value | Lookup by one key: sessions, config, counters, caches | Redis, DynamoDB, Memcached (cache only) | No ad-hoc queries; design keys up front |
| Document | Self-contained records with evolving shape: catalogs, content, profiles | MongoDB, CouchDB, Firestore | Cross-document joins/transactions are weak or costly; duplicated data drifts |
| Wide-column | Huge write volume, known query paths, time-ordered or partition-keyed data | Cassandra, HBase, Bigtable, ScyllaDB | Query-first modelling; no joins; eventual consistency by default |
| Graph | Relationship traversal is the query: social, recommendations, fraud rings, dependencies | Neo4j, ArangoDB, Neptune | Poor for bulk aggregates; hard to shard |
| Time-series | Timestamped metrics/telemetry, range queries, downsampling, retention | InfluxDB, TimescaleDB, Prometheus | High-cardinality labels blow up storage |
| Search | Full-text, relevance ranking, faceting, log search | Elasticsearch, OpenSearch, Solr | A derived index, not a source of truth; lag behind the primary |
| In-memory | Microsecond latency, ephemeral or rebuildable data | Redis, Memcached | RAM cost; durability depends on config (section 10) |
| NewSQL | SQL and ACID transactions with horizontal scale or multi-region | CockroachDB, Google Spanner, TiDB, YugabyteDB | Cross-region write latency; younger ecosystems |
| Object-oriented | Rich object graphs persisted as-is (niche) | ObjectDB, db4o | Rarely worth the lock-in; an ORM plus RDBMS usually wins |

Rule of thumb: if you cannot name the access pattern that a relational database fails at, use a relational database (Postgres covers JSON, full-text, and time-series well enough to start). Add a specialized store when a measured need appears, and treat it as derived data fed from the system of record.

## 4. SQL vs NoSQL decision table

The category does not guarantee behavior. Check the actual product's consistency, transaction and scaling settings.

| Driver | Leans SQL | Leans NoSQL |
|---|---|---|
| Access pattern | Many query shapes, joins, ad-hoc reporting | A few known queries, mostly by key or partition |
| Data shape | Stable, relational, constraints matter | Evolving, nested, or varied per record |
| Consistency | Multi-row/multi-table transactions (payments, inventory) | Single-record atomicity is enough; eventual consistency tolerated |
| Scale | One primary plus read replicas fits the volume | Write volume or data size beyond one node; need linear scale-out |
| Latency | Milliseconds acceptable | Predictable single-digit ms at scale, or in-memory speed |
| Team/ops | Mature tooling, familiar SQL | Team knows the product and its modelling rules |
| Schema change | Migrations are acceptable (section 11) | Frequent shape changes; but the app still needs a versioning plan |

In the design doc: list the top queries, the write rate, the consistency each operation needs, the expected size in 1 and 3 years, and what you chose and why. If the answer is "NoSQL for scale", show the number that a single relational node cannot meet.

## 5. File vs database storage; block, object, file storage

**File storage vs database storage**
- Files in folders: simple and cheap, fit unstructured blobs (images, video, PDFs, logs, exports); no query engine, no constraints, hard to keep consistent across files.
- Database: querying, indexing, constraints, concurrent updates, transactions; more setup and cost.
- Common split: the large binary goes in object/file storage, the database keeps its metadata and the URL/key. Delete and update both sides together, and plan orphan cleanup. Avoid big blobs inside OLTP rows (bloats backups and the buffer cache).

| Storage | What it is | Use for | Examples |
|---|---|---|---|
| Block | Raw fixed-size blocks attached to a server; a filesystem or DB manages them | Database data volumes, VM disks, low-latency transactional I/O | AWS EBS, Google Persistent Disk, SAN |
| Object | Whole objects (data + metadata + ID) in a flat namespace, accessed over HTTP API; usually immutable-by-replace | Media, backups, logs, data lakes, static assets, user uploads | Amazon S3, Azure Blob, Google Cloud Storage |
| File | Hierarchical files and directories accessed by path, shared over a network | Shared documents, home directories, shared workspaces, legacy apps expecting a filesystem | NAS, Amazon EFS, Azure Files, Google Filestore |

Pick: database engine files go on block; user uploads and backups go to object; a shared mount for several servers is file. Object storage is not a filesystem: no partial in-place edits, rename is copy+delete, and listing is slow at scale.

## 6. Normalization and denormalization

One-line rules (each form includes the previous):

| Form | Rule | Fixes |
|---|---|---|
| 1NF | One atomic value per column; no repeating groups or comma lists | Multi-valued cells |
| 2NF | Every non-key column depends on the whole key, not part of a composite key | Partial dependency |
| 3NF | Non-key columns depend on the key only, not on other non-key columns | Transitive dependency |
| BCNF | Every determinant (left side of a dependency) is a candidate key | Leftover anomalies when keys overlap |
| 4NF / 5NF | No independent multi-valued facts in one table / no lossless-join leftovers | Rare; know they exist |

Running example, a single table `orders(order_id, items, customer_id, customer_city, product_id, product_name)`:
- 1NF: `items` held "A,B,C" → one row per order line: `order_lines(order_id, product_id, ...)`.
- 2NF: with key (order_id, product_id), `product_name` depends only on product_id → move to `products`.
- 3NF: `customer_city` depends on customer_id, not on the order → move to `customers`.
- BCNF: if each teacher teaches one course and the table is keyed (student, course), teacher determines course but is not a key → split into (student, teacher) and (teacher, course).

Why it matters: duplicated facts cause update, insert and delete anomalies (change a city in 1 of 5 rows; cannot add a product with no orders; deleting the last order erases the product). Default target is 3NF; go to BCNF when keys overlap.

**Denormalization**: deliberately store redundant data to shorten the read path. Do it only after `EXPLAIN` or profiling shows joins or aggregates are the bottleneck.

| Technique | Example | Cost |
|---|---|---|
| Duplicate a column into the reader's table | `order.customer_name` copy | Must update on change; stale copies |
| Precomputed value | `orders.total`, `posts.like_count` | Keep in sync on every write path |
| Summary / rollup table | daily sales per product | Refresh job or trigger; lag |
| Merge tables that are always joined | 1:1 tables into one | Wider rows, harder schema change |
| Materialized view | stored result of a heavy query | Refresh cost; stale between refreshes |

Justifies it: read-heavy, rarely-changing data, expensive multi-join queries on big tables, reporting. Avoid when data changes often, strict consistency across copies is required, or the normalized query is already fast enough. Keep the normalized tables as source of truth, name the owner of each derived field, and add a test or reconciliation query that detects drift. Alternative to consider first: an index, a cache (`caching.md`), or a read replica.

## 7. SQL query optimization checklist

Measure first: run `EXPLAIN` (or the engine's equivalent) on the slow query with realistic data. `EXPLAIN ANALYZE` in PostgreSQL really executes the statement, so wrap writes in a transaction you roll back.

- [ ] Index the real predicates: columns in WHERE, JOIN and ORDER BY; composite index column order matches equality columns first, then range/sort. Check unused or duplicate indexes; each costs writes.
- [ ] Select only needed columns; avoid `SELECT *` (more I/O, breaks covering indexes, couples code to schema).
- [ ] Keep predicates sargable: no function or arithmetic on the indexed column (`WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01'`, not `YEAR(created_at) = 2026`); no implicit type casts; no leading wildcard `LIKE '%x'` (use full-text or trigram index when needed). Rewriting a predicate must keep the same results.
- [ ] Filter early and cap results: WHERE plus LIMIT (`TOP`/`FETCH FIRST` on other dialects).
- [ ] Joins: join only what you need, on indexed keys; INNER JOIN when unmatched rows are not wanted. Use `EXISTS` for "is there any match" checks; modern optimizers often treat IN/EXISTS alike, so confirm with the plan.
- [ ] Prefer a join or a single batched `WHERE id IN (...)` over per-row subqueries; correlated subqueries run per outer row when not flattened.
- [ ] Pagination: use keyset (`WHERE (created_at, id) < (:last_created, :last_id) ORDER BY created_at DESC, id DESC LIMIT 50`) instead of large `OFFSET`, which scans and discards rows.
- [ ] N+1: one query for the list, then one per row. Fix with a join, `IN` batch, or ORM eager loading (`select_related`, `include`, `joinedload`). Look for it in query logs: the same statement repeated with different ids.
- [ ] Batch writes: multi-row INSERT, bulk/COPY loaders, or batched UPDATEs in a transaction instead of one round trip per row; keep batches bounded to avoid long locks.
- [ ] `UNION ALL` instead of `UNION` only when duplicates are impossible or acceptable (results differ).
- [ ] Watch deep aggregates: pre-aggregate, or use a summary table / materialized view (section 6).
- [ ] Re-check after the change: compare plan and timing before and after, and keep the new index in a migration.

## 8. Replication

Copies of data on several nodes for availability, read scaling, disaster recovery, and locality. Replication is not a backup: a bad write or `DROP` replicates too, so keep point-in-time backups as well.

**Topologies**

| Topology | How | Good for | Trade-offs |
|---|---|---|---|
| Leader-follower (primary-replica, master-slave) | One node takes writes; followers copy and serve reads | Read-heavy apps, simple failover | Write bottleneck at the leader; read-your-writes issues on replicas |
| Multi-leader (master-master) | Several nodes accept writes and sync | Multi-region writes, offline-capable clients | Write conflicts; complex ordering and conflict rules |
| Leaderless (Dynamo-style: Cassandra, Riak, DynamoDB) | Any replica takes writes; quorum reads/writes (R + W > N) | High availability, no failover step | Eventual consistency; read repair, tunable quorums; sloppy quorums can return stale data |

**Timing modes**

| Mode | Behavior | Trade-off |
|---|---|---|
| Synchronous | Commit waits for replica ack | No loss on leader failure; latency and availability cost if a replica is slow |
| Asynchronous | Commit returns immediately | Fast; replicas lag; committed writes can be lost on failover |
| Semi-synchronous | At least one replica acks synchronously, the rest async | Common compromise: bounded loss, bounded latency |

**Other types named in the sources (mostly SQL Server-style publishing terms):** snapshot (full point-in-time copy on a schedule; simple, stale between runs, good for reporting), transactional (stream each change to subscribers; fresh, more setup), merge (nodes update independently then reconcile; for intermittently connected clients, needs conflict rules). Logical replication (row changes) vs physical (WAL/binlog bytes) is a separate axis: logical allows cross-version and selective tables, physical is exact and cheaper.

**What to handle in code and design**
- Replication lag: reads from a replica may be stale. Route read-after-write paths (user just saved something, payments, auth) to the leader or use session stickiness/LSN-based reads; expose lag as a metric with an alert.
- Failover: how it is detected, who is promoted, how clients find the new leader (DNS, proxy, driver). Test it. Beware split brain (two leaders): use fencing and a quorum-based election. With async replication, promoted replicas may lack the last writes.
- Conflict resolution (multi-leader/leaderless): last-write-wins loses data and depends on clocks; alternatives are version vectors, CRDTs, per-record home region, or app-level merge. Prefer designs that avoid concurrent writes to the same record.
- Replicas serve reads only; make the connection layer explicit (read vs write pool) and keep migrations on the leader.
- Capacity: every replica applies all writes, so replication scales reads, not writes. For write scale see section 9.
- See `availability-and-consistency.md` for CAP and consistency models and `distributed-systems.md` for consensus and failure modes.

## 9. Partitioning and sharding

Partitioning splits a big dataset into smaller parts. Sharding is horizontal partitioning where the parts live on different nodes. Try, in order: indexes and query fixes, caching, read replicas, vertical scale, in-database partitioning, and only then sharding. Sharding makes every later change harder.

| Kind | Split by | Use when |
|---|---|---|
| Horizontal | Rows (by key, range, or hash) | A table is too big or hot for one node; same schema in each part |
| Vertical | Columns (hot narrow columns apart from wide or rarely read ones, e.g. blobs) | Rows are wide and queries touch few columns |
| Functional | Feature/domain (users DB, orders DB, analytics DB) | Domains scale independently or have different owners; this is the step toward microservices |

Single-node table partitioning (Postgres, MySQL) by date range is a cheap first step: smaller indexes, partition pruning, and instant retention by dropping an old partition.

**Sharding strategies**

| Strategy | How | Pros | Cons |
|---|---|---|---|
| Hash / key | `hash(key) mod N` or consistent hashing | Even spread, simple routing | Range queries scatter; modulo reshuffles on resize (use consistent hashing or many virtual shards; see `load-balancing.md`) |
| Range | Contiguous key ranges per shard | Efficient range scans, easy to split a range | Hot shard for sequential keys (time, auto-increment) |
| Directory / lookup | Table maps key → shard | Flexible placement, easy to move tenants | Lookup is a dependency and extra hop; must be cached and highly available |
| Geographic | By region/country | Low latency, data residency | Uneven load, cross-region queries are hard |

**Choosing a shard key** (the decision that is hardest to undo)
- Appears in the hot queries, so most requests hit one shard (tenant_id, user_id, account_id).
- High cardinality and even distribution of both data and traffic; avoid keys with a few giant values (a celebrity user, one huge tenant).
- Immutable, or rarely changed (changing it means moving the row).
- Not monotonic if writes are heavy (timestamps/auto-increment on range sharding create a write hotspot); use hash or a composite (shard by tenant, order by time inside).
- Test it: take real or modelled traffic and compute the per-shard load and the share of queries that need more than one shard.

**Problems to plan for**
- Hot shards: skewed keys or traffic. Mitigate with a better key, key salting, splitting heavy tenants onto their own shard, caching.
- Rebalancing/resharding: moving data while serving traffic. Use many small logical shards mapped to few machines, so a move is reassigning a logical shard; do online copy then cutover with dual writes or change-data-capture, then verify.
- Cross-shard joins and aggregates: avoid by design (co-locate related rows on the same key; replicate small reference tables to every shard); otherwise scatter-gather in the app or a separate analytics store.
- Cross-shard transactions: expensive (two-phase commit) or unavailable; prefer designs where one transaction stays in one shard, or use sagas with compensation (`distributed-systems.md`).
- Globally unique IDs and constraints: unique constraints only hold within a shard; use snowflake-style or UUID/ULID ids.
- Operations: backups, schema migrations (run on every shard, partial failure state), monitoring per shard, connection routing. Add a router/library and test the "one shard is down" path.
- Related scaling topics: `scalability.md`.

## 10. Redis

In-memory data-structure server. Fast because data is in RAM and commands are simple and run in one main thread (newer versions add I/O threads); that also means one slow command blocks everyone.

| Structure | Use cases |
|---|---|
| String | Cache values, counters (`INCR`), locks (`SET key val NX PX ttl`), serialized objects |
| Hash | Objects/profiles with field updates |
| List | Simple queues, recent-activity feeds |
| Set | Tags, membership checks, unique visitors |
| Sorted set | Leaderboards, ranking, time-ordered indexes, delayed jobs |
| Stream | Append-only event log with consumer groups |
| Others (JSON, geo, HyperLogLog, bitmaps, pub/sub) | Documents, nearby search, approximate counts, flags, fan-out notifications |

Common roles: cache-aside (check Redis, on miss read DB and set with TTL), session store, rate limiter, counters, leaderboard, lightweight queue. Strategies and invalidation are in `caching.md`.

**Persistence**
- RDB: periodic point-in-time snapshots; compact, fast restart, can lose the writes since the last snapshot.
- AOF: log of writes replayed on restart; with `appendfsync everysec` it loses about a second, with `always` it is safest and slowest; needs rewrite to compact.
- Both together are common. Pure cache: persistence can be off. Primary store: decide the acceptable loss, and still keep the system of record elsewhere unless Redis is truly the source.

**Eviction and expiry**
- TTL expiry is per key; eviction applies when `maxmemory` is reached. Always set `maxmemory`.
- Policies: `noeviction` (writes fail when full), `allkeys-lru` / `allkeys-lfu` (cache default), `volatile-*` (only keys with TTL), `allkeys-random`, `volatile-ttl`. Use an `allkeys-*` policy for a cache; `volatile-*` with keys lacking TTL silently fills memory.

**Replication and scaling** (not detailed on the source page; standard Redis behavior)
- Leader-follower replication is asynchronous, so a failover can drop recent writes. Sentinel monitors and promotes a replica; Redis Cluster shards keys over 16384 hash slots across masters (each with replicas). Multi-key operations and transactions must stay within one slot (use `{hash tags}`).

**Pitfalls**
- Missing TTLs and unbounded keys/collections; big keys (huge list/hash) cause latency spikes and uneven cluster load.
- `KEYS *` and other O(N) commands in production; use `SCAN`.
- Stale cache after writes: define invalidation; add jitter to TTLs to avoid mass expiry and stampedes.
- Treating Redis as durable by default; or storing data you cannot rebuild.
- No joins or ad-hoc queries; do not make it a relational substitute. Memory is costly: estimate bytes per key times keys.
- Secure it: auth/ACLs, bind to private network, TLS. An open Redis is a frequent breach.

## 11. Changing an existing schema (migrations)

- Use the project's migration tool (Alembic, Django, Prisma, Flyway, Rails, Knex…). Never hand-edit a production schema.
- Make migrations **reversible** (down/rollback) or say why they can't be.
- Zero-downtime pattern for risky changes — **expand → migrate → contract**:
  1. Add the new column/table (nullable or with default); code writes both old and new.
  2. Backfill existing rows in batches; verify counts.
  3. Switch reads to the new shape.
  4. Remove the old column in a later release.
- Adding NOT NULL / unique / foreign key to a big table: check existing data first; some engines lock the table.
- Create indexes concurrently where supported (`CREATE INDEX CONCURRENTLY` in Postgres) to avoid blocking writes.
- Renames are drop + add to most clients — use expand/contract.
- Sharded or replicated databases: apply to every shard; keep old and new code compatible during rollout.

## 12. Data conversion and loading
- Batch large backfills; make them idempotent and resumable (checkpoint the last processed id).
- Validate after loading: row counts, checksums or sample comparisons, constraint checks.
- Keep the source until the new data is verified.

## 13. Testing
- Run migrations up **and** down against a copy/fixture DB.
- Test queries against realistic volumes when performance matters (`EXPLAIN` the hot queries).
- Tests for constraints: inserting invalid data must fail.
- Replicated setups: test a read right after a write on a replica and a failover.

## 14. Checklist
- [ ] Access patterns, volumes and consistency needs listed before choosing database type, schema and indexes
- [ ] Database type justified against the decision table (and the number that rules out the simpler option)
- [ ] Constraints enforce invariants in the DB
- [ ] Normalized to 3NF; each denormalized field has a measured reason, an owner and a drift check
- [ ] Hot queries checked with EXPLAIN: sargable predicates, needed columns only, keyset pagination, no N+1, batched writes
- [ ] Large blobs in object storage, with metadata in the database
- [ ] Replication mode chosen (sync/async/semi-sync); lag, read-after-write routing, failover and conflict handling designed; backups separate
- [ ] Sharding only after simpler options; shard key evaluated for distribution, hot queries, immutability; cross-shard joins/transactions and rebalancing planned
- [ ] Redis (if used): maxmemory and eviction policy set, TTLs on cache keys, persistence matches the loss tolerance, no O(N) commands in hot paths
- [ ] Migration reversible, tested up and down
- [ ] Large changes use expand → migrate → contract
- [ ] Backfill batched, idempotent, verified
