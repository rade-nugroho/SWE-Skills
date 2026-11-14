# Networking for engineers

## Contents
1. Protocol chooser
2. Real-time decision guide
3. WebSocket vs HTTP
4. DNS
5. DNS caching, TTL trade-offs, flushing
6. TTL in other senses
7. CDN
8. Forward vs reverse proxy
9. Web server vs application server
10. Network debugging quick list
11. Checklist

Related: `caching.md` (CDN/edge cache strategy), `load-balancing.md`, `api-gateway-queues-rate-limits.md`, `security.md` (TLS), `distributed-systems.md`.

## 1. Protocol chooser

Pick by what the traffic needs (latency, ordering, direction, fan-out), not by fashion. Default to HTTPS + JSON REST for public request/response APIs and add something else only for a stated reason.

| Option | Good at | Pick it when | Watch out for |
|---|---|---|---|
| TCP | Reliable, ordered byte stream | Almost everything: HTTP, DB, SSH | Handshake cost, head-of-line blocking when a packet is lost |
| UDP | No handshake, no ordering, low overhead | Live audio/video, games, DNS, telemetry that tolerates loss | You build any reliability yourself; firewalls often drop it |
| HTTP/1.1 | Universal, easy to debug | Default fallback, simple services | One request at a time per connection; browsers open ~6 connections per host |
| HTTP/2 | Multiplexed streams over one TCP connection, header compression | Many small requests from browsers; gRPC | One lost TCP packet stalls all streams |
| HTTP/3 | HTTP over QUIC (UDP): per-stream loss recovery, faster connection setup | Mobile/lossy networks, global users; turn on at the CDN/LB | UDP may be blocked, so clients must fall back to HTTP/2 |
| REST (JSON over HTTP) | Resource-oriented CRUD, cacheable GETs, any client | Public APIs, CRUD services | Over/under-fetching, chatty for nested data |
| gRPC | Typed contracts (protobuf), streaming, small payloads, HTTP/2 | Internal service-to-service calls, polyglot teams | Browsers need gRPC-Web or a proxy; harder to curl; LBs must be HTTP/2-aware |
| GraphQL | Client picks fields; one round trip for nested data | Many client types with different data needs | Caching is harder, query cost/depth limits needed, N+1 on the server |
| Short polling | Plain HTTP on a timer | Updates where a delay of seconds is fine | Mostly empty responses, wasted load |
| Long polling | Near-real-time over plain HTTP | Push needed but SSE/WebSocket blocked or unavailable | Many held-open requests, reconnect logic |
| Server-Sent Events (SSE) | One-way server-to-client stream over HTTP, built-in reconnect in browsers | Notifications, progress, live feeds, LLM token streaming | One direction only; text only; per-host connection limit on HTTP/1.1 |
| WebSocket | Two-way messages over one long-lived connection | Chat, collaborative editing, games, live trading UIs | Stateful connections, harder scaling and deploys (sections 2-3) |
| MQTT | Tiny pub/sub protocol with QoS levels, built for flaky links | IoT devices, sensors, mobile push-like telemetry | Needs a broker; not for request/response |
| AMQP | Broker messaging with routing, acks, queues (RabbitMQ) | Reliable async work between services | Operating a broker; at-least-once means idempotent consumers |

Sync vs async is a separate axis: use synchronous calls when the caller needs the answer now (auth, payment authorization); use a queue or event when work can finish later (email, reports). Synchronous chains tie your availability to every downstream, so set timeouts and retries. See `event-driven.md`.

## 2. Real-time decision guide

Walk down the list and stop at the first option that meets the requirement.

| Step | Use | Because | Costs to plan for |
|---|---|---|---|
| 1 | Short polling | A delay of N seconds is acceptable; simplest, cache-friendly | Request rate = clients / interval. 10k clients at 5 s is 2k req/s of mostly empty answers. Add jitter and conditional requests (ETag / 304) |
| 2 | Long polling | Need update within about a second, must work through any proxy | One held connection per client; set server timeout below proxy/LB idle timeout (e.g. 30 s vs 60 s); client re-requests immediately after each response, with backoff on errors |
| 3 | SSE | Server pushes, client rarely sends (send via normal POST) | One long-lived connection per client; proxies must not buffer the stream; use heartbeat comments and `Last-Event-ID` to resume |
| 4 | WebSocket | True two-way, low-latency, high message rate | Stateful connection per client; needs ping/pong heartbeats, reconnect with backoff and resync, sticky or fan-out design |

Things that bite in all long-lived options:
- **Connection count** is the capacity limit, not CPU. Check file-descriptor limits, memory per connection, and LB max connections. Estimate: concurrent users x connections each.
- **Proxy and LB idle timeouts** silently kill quiet connections (often 60 s). Send a heartbeat more often than the shortest timeout on the path.
- **Reverse proxy config** must allow streaming: disable response buffering for SSE, forward the `Upgrade` and `Connection` headers for WebSocket, raise read timeouts.
- **Reconnect logic is part of the feature.** Client: exponential backoff with jitter (so a server restart does not cause a thundering herd), resend or resync missed state. Server: assign message IDs or offsets so the client can ask "everything since X".
- **Fan-out across servers:** a user's connection lives on one node, so an event produced elsewhere needs a pub/sub backplane (Redis pub/sub, Kafka, NATS) to reach it.
- **Deploys** drop every connection on the node; drain gracefully and expect a reconnect wave.
- **Auth:** browsers cannot set custom headers on WebSocket or `EventSource` handshakes, so use a cookie or short-lived token in the first message or query string (and keep tokens out of logs).

## 3. WebSocket vs HTTP

| Aspect | HTTP | WebSocket |
|---|---|---|
| Model | Client asks, server answers | Either side sends at any time |
| Connection | Request/response; connections reused via keep-alive or multiplexing | One persistent connection after upgrade |
| Setup | Plain request | HTTP request with `Upgrade: websocket`; server replies `101 Switching Protocols`; then the framing protocol takes over |
| Direction | Half-duplex per exchange | Full duplex (both directions at once) |
| State | Stateless by design; any server can answer | Connection is stateful and pinned to one server |
| Caching, retries, status codes | Built in | None; you define message formats, errors, and acks |
| Scaling | Add stateless nodes behind an LB | Capacity = open connections; need backplane, drain on deploy |
| Encryption | HTTPS | WSS (TLS), same certificates |

Design consequences:
- A stateless HTTP API can be load-balanced with round robin; WebSocket nodes hold per-connection state (subscriptions, user identity), so keep durable state elsewhere (DB, Redis) and treat the socket as a transport that can vanish.
- Define a message envelope early: `{type, id, payload}`, version it, and handle unknown types.
- Add application-level acks if delivery matters; a successful `send()` only means the bytes left your side.
- Apply rate limits and size limits per connection; one bad client can otherwise flood a node.
- Keep a plain HTTP fallback (long polling or SSE) if clients sit behind restrictive corporate proxies.

## 4. DNS

DNS turns a name into records. Know the path so you can tell which hop is stale or broken.

Resolution path (all caches empty):
1. App checks its own cache, then the OS stub resolver cache (and `/etc/hosts`).
2. Stub asks the **recursive resolver** (ISP, corporate, or public like 1.1.1.1 / 8.8.8.8).
3. Resolver asks a **root server**, which refers it to the **TLD servers** (`.com`).
4. TLD servers refer it to the domain's **authoritative servers** (the NS records).
5. Authoritative server answers; the resolver caches the answer for its TTL and returns it.

The client-to-resolver query is usually recursive (resolver does the work); resolver-to-servers queries are iterative (each returns an answer or a referral).

| Record | Meaning | Engineering use |
|---|---|---|
| A | Name to IPv4 address | Point a host at servers |
| AAAA | Name to IPv6 address | Publish if you serve IPv6; a broken AAAA causes slow or failing connections for IPv6 clients |
| CNAME | Alias to another name | `www` or `api` to a vendor/CDN hostname. Not allowed at the zone apex alongside other records; use your DNS provider's ALIAS/ANAME feature there |
| MX | Mail servers, with priority | Email routing |
| TXT | Free text | SPF/DKIM/DMARC, domain-ownership verification, ACME DNS challenges |
| NS | Which servers are authoritative for the zone | Delegation; wrong NS at the registrar breaks everything |
| PTR | IP to name (reverse DNS) | Mail reputation, logs; a weak signal, not proof of identity |

DNS-based load balancing and failover:
- **Round robin:** several A/AAAA records for one name; clients pick among them. Cheap, but it knows nothing about server health or load, and caches pin clients to one answer.
- **Weighted / latency / geo routing:** managed DNS services (Route 53, Cloudflare, NS1) answer by weight, client location, or latency.
- **Health-checked failover:** the provider probes your endpoints and withdraws unhealthy ones. Recovery time is bounded below by the record TTL plus resolvers that ignore it, so it is minutes, not seconds. Use a low TTL (30-60 s) on records that fail over.
- Use DNS to steer between regions or fleets; use an L4/L7 load balancer (`load-balancing.md`) for per-request balancing and fast health ejection.

## 5. DNS caching, TTL trade-offs, flushing

Cache layers, nearest first: application/runtime (some languages and HTTP clients cache lookups, e.g. the JVM) then browser, OS resolver, local forwarder (dnsmasq, systemd-resolved), recursive resolver. The root/TLD/authoritative walk is the miss path, not a cache. Failed lookups (NXDOMAIN) are cached too ("negative caching"), so a name you just created may stay "not found" for a while.

| TTL | Benefit | Cost |
|---|---|---|
| Long (hours-day) | Fewer queries, faster lookups, less load on authoritative servers, survives short provider outages | Changes take that long to reach everyone |
| Short (30-300 s) | Changes and failover propagate fast | More queries, higher DNS bill/latency, more exposure if the DNS provider is down |

Practical rules:
- Stable records: 1 h or more. Records you may need to move or fail over: 60-300 s.
- Planned migration: lower the TTL at least one old-TTL period before the cutover (if the TTL is 24 h, lower it 24 h ahead), switch the record, verify, then raise the TTL again. Lowering it only at cutover does nothing for resolvers that already cached the old value.
- Some resolvers and clients clamp or ignore TTLs, so keep the old target running for a while after cutover.
- Do not rely on DNS for instant switchover; add an LB or proxy in front when you need that.

Flushing a cache (clears your machine only, not the resolver or other users):

| OS | Command |
|---|---|
| macOS | `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` |
| Windows | `ipconfig /flushdns` (view with `ipconfig /displaydns`) |
| Linux, systemd-resolved | `sudo resolvectl flush-caches` (older: `sudo systemd-resolve --flush-caches`) |
| Linux, other | restart the local cache: `sudo systemctl restart dnsmasq` or `sudo nscd -i hosts` |
| Chrome | open `chrome://net-internals/#dns` and clear host cache |

When flushing is the right step: a record changed and only your machine or browser still reaches the old IP; you hit a cached NXDOMAIN for a just-created name; you edited `/etc/hosts`. First prove it is a local cache: `dig example.com +short` (queries the resolver directly, skipping the OS cache) shows the new IP while `ping`/`curl` use the old one. If `dig` also shows the old IP, the resolver holds it; flushing locally will not help, so query the authoritative server (`dig @ns1.example.com example.com`) and wait out the TTL. Flushing is not a performance or security measure.

## 6. TTL in other senses

| Sense | What it is | Where it matters |
|---|---|---|
| IP TTL (IPv6: hop limit) | Counter in the packet header, decremented by each router; at 0 the packet is dropped and an ICMP "time exceeded" goes back | Stops routing loops; `traceroute` sends probes with TTL 1, 2, 3... to reveal each hop. A packet starting at TTL N crosses at most N-1 routers before the next one drops it |
| DNS TTL | Seconds a resolver may cache a record | Section 5 |
| HTTP cache lifetime | `Cache-Control: max-age=...` (and `s-maxage` for shared caches) | Browser and CDN freshness; `no-store` means do not cache; `max-age=0` means revalidate |
| Application cache expiry | Redis `EXPIRE`/`SET ... EX`, memcached expiry | Bounds staleness; add jitter so keys do not expire together (`caching.md`) |
| Others | Message TTL in brokers, session/token lifetime, service-discovery leases | Pick values from how stale the data may be, not a default |

## 7. CDN

A CDN is a fleet of edge servers near users. A request is routed (via DNS or anycast) to a nearby edge; a cache hit is served there, a miss is fetched from your origin (often via a mid-tier cache), stored per policy, and returned. Benefits: lower latency, origin offload, absorbing traffic spikes, TLS termination and DDoS filtering at the edge.

| | Pull | Push |
|---|---|---|
| How | Edge fetches from origin on first request | You upload content to CDN storage ahead of time |
| Fits | Most websites and APIs with cacheable GETs | Large known files: installers, video releases |
| Cost | First request per edge is slow; origin must handle misses | You manage uploads and removal |

What to put on it: fingerprinted static assets (`app.3f9a1c.js`) with long `max-age` and `immutable`; images and video (with resizing at the edge); public downloads; cacheable public API GETs with short TTLs. Keep off it, or bypass: responses with `Set-Cookie`, per-user pages, anything carrying auth.

Cache keys and purging:
- The cache key is normally scheme + host + path + query string. Make it explicit: ignore tracking params (`utm_*`), include only the headers or cookies that change the response (e.g. `Accept-Encoding`, language), and never put session cookies in the key.
- Prefer new URLs over purges: content-hash filenames make invalidation unnecessary for assets. HTML gets a short TTL or `stale-while-revalidate`.
- When you must purge: by URL, by tag/surrogate key, or by prefix. Purges are eventually consistent across edges and may be rate-limited or billed.

Pitfalls with personalized content:
- Caching a response that contains one user's data and serving it to another is a data leak. Send `Cache-Control: private` (or `no-store`) on personalized responses, and use `Vary` correctly.
- A wide `Vary` (e.g. `Vary: Cookie`) makes the hit rate collapse; split the page into a cached shell plus a small uncached per-user call.
- Check that origin errors (5xx) are not cached for long; use `stale-if-error` if you want a graceful fallback.
- Lock the origin to CDN traffic (allowlist CDN IPs or use a shared secret header) so attackers cannot bypass it.

Details on TTL choice, stampedes, and invalidation: `caching.md`.

## 8. Forward proxy vs reverse proxy

| | Forward proxy | Reverse proxy |
|---|---|---|
| Acts for | Clients | Servers |
| Sits | In front of clients, toward the internet | In front of your backends, toward clients |
| Who configures it | Client or network (explicit or transparent) | Server operator; clients are unaware |
| Typical jobs | Egress control, content filtering, outbound caching, audit logs, hiding client IPs (not real anonymity) | Load balancing, TLS termination, routing by host/path, caching, compression, rate limiting, WAF |
| Examples | Squid, corporate egress proxy | Nginx, HAProxy, Envoy, Traefik, cloud LBs, CDNs |

What a reverse proxy gives you: one public entry point; backends hidden behind private IPs; TLS handled in one place; routing (`/api` to one service, `/` to another); health checks and retries; buffering of slow clients; easy canary and blue-green switches; a place for auth, rate limits, and request logging. Costs: an extra hop, a potential bottleneck and single point of failure (run at least two), and one more config surface.

Code-level consequences:
- Backends see the proxy's IP. Read the client address from `X-Forwarded-For` / `Forwarded` and the scheme from `X-Forwarded-Proto`, but trust these headers only from your own proxy (strip them at the edge, configure trusted hops in the framework).
- Build absolute URLs and redirects from the forwarded host/scheme, or you will emit `http://` links behind a TLS-terminating proxy.
- Set proxy timeouts consistently: client timeout > proxy timeout > upstream call timeout, or you get duplicated work and mystery 502/504s.
- Outbound calls from your service in a corporate network may need `HTTPS_PROXY` / `NO_PROXY` set.

## 9. Web server vs application server

| | Web server | Application server |
|---|---|---|
| Job | Accept HTTP(S), serve static files, route, terminate TLS, proxy | Run business logic, talk to DB and other services, manage sessions/transactions |
| Typical products | Nginx, Apache httpd, Caddy, IIS | Java/Jakarta: Tomcat, Jetty, WildFly, WebLogic, WebSphere; Python: Gunicorn/uWSGI; Node: Express/Fastify process; .NET: Kestrel |
| Strength | Many cheap concurrent connections, static speed | Dynamic request handling in your language |
| Scale by | More nodes plus CDN | More stateless nodes; tune worker/thread pools |

Combined pattern: client to CDN to Nginx (TLS, static files, gzip, rate limit) to app server(s) to DB. Modern runtimes (Node, Go, Kestrel) can face the internet directly, but a reverse proxy in front still adds TLS management, buffering, and routing. The lines blur (Nginx also proxies and balances; Tomcat can serve files), so decide by responsibility: edge concerns in the proxy, business logic in the app.

## 10. Network debugging quick list

Work from the name outward. Change one thing at a time and record each result.

| Question | Check | Reading the result |
|---|---|---|
| Does the name resolve? | `dig example.com +short`; `nslookup example.com` | Empty or NXDOMAIN: DNS problem. Compare `dig @8.8.8.8 example.com` against your default resolver |
| Is it a local DNS cache? | `dig` vs `getent hosts example.com` (Linux) or `dscacheutil -q host -a name example.com` (macOS) | Different answers mean the OS/browser cache is stale (flush) |
| Where does resolution break? | `dig +trace example.com`; `dig example.com NS` | Shows each delegation step; wrong NS or lame server |
| Which record is served? | `dig example.com A`, `AAAA`, `CNAME`, `MX`, `TXT` | Check for a stray AAAA or old CNAME |
| Can I reach the port? | `nc -vz host 443` (Windows: `Test-NetConnection host -Port 443`) | Refused: nothing listening. Timeout: firewall, security group, or route |
| Is the path OK? | `traceroute host` (Windows: `tracert host`); `mtr host` | Where latency jumps or probes stop (many routers drop probes, so stars are not proof) |
| Is TLS the problem? | `curl -v https://host/`; `openssl s_client -connect host:443 -servername host` | Handshake errors, expired or wrong-name cert, missing intermediate, protocol mismatch |
| Where does time go? | `curl -sS -o /dev/null -w 'dns %{time_namelookup} connect %{time_connect} tls %{time_appconnect} ttfb %{time_starttransfer} total %{time_total}\n' https://host/` | Large `dns` = resolver; large `connect` = network; large `tls` = handshake; large gap to `ttfb` = slow backend |
| Is a proxy involved? | `env \| grep -i proxy`; `curl -v -x http://proxy:8080 https://host/`; `curl --noproxy '*' https://host/` | Works with one and not the other: proxy config or proxy filtering |
| Does the app or the edge fail? | `curl -sI https://host/` (look at `server`, `via`, `x-cache`, `age`); `curl --resolve host:443:ORIGIN_IP https://host/` | Bypass DNS/CDN to hit a specific IP and test the origin directly |
| Timeout or reset? | `curl -v --connect-timeout 5 --max-time 20 URL` | "Connection timed out" in connect = packets dropped; "reset by peer" = something actively closed it; 502/504 = proxy cannot get a good upstream response |
| Firewall? | Same port from another host/network; check security groups and host firewall (`sudo iptables -S` or `sudo nft list ruleset` on Linux) | Works from inside but not outside: ingress rule |

Common symptoms: works by IP but not by name is DNS; works with `-k` is a certificate problem; slow first request then fast is DNS or TLS setup, or a cold cache; intermittent failures across a pool is often one bad backend or one stale DNS answer.

## 11. Checklist

Design docs:
- [ ] Protocol per link chosen with a reason (sync vs async, REST/gRPC/GraphQL, polling/SSE/WebSocket).
- [ ] Real-time features: peak concurrent connections estimated, idle timeouts and heartbeat interval set, reconnect and resume behavior defined, fan-out path across nodes drawn.
- [ ] DNS: records, TTLs, and who owns the zone listed; failover plan states the real recovery time.
- [ ] Migration plan lowers TTL ahead of the change and keeps the old target alive afterward.
- [ ] CDN: what is cacheable, cache key, TTLs, purge method, and what is explicitly excluded (personalized data).
- [ ] Reverse proxy/LB redundant; timeouts ordered client > proxy > upstream.
- [ ] TLS terminates where stated, and the hop after it is protected as required (`security.md`).

Code:
- [ ] Every outbound call has a connect timeout and a total timeout.
- [ ] Client IP and scheme come from trusted forwarded headers only.
- [ ] Responses carry correct `Cache-Control` and `Vary`; personalized ones are `private` or `no-store`.
- [ ] Long-lived connections send heartbeats, back off with jitter, and tolerate server restarts.
- [ ] Runtime/HTTP-client DNS caching checked (long-lived processes can hold a stale IP past the TTL).
- [ ] Debugging done name-first: DNS, then port, then TLS, then HTTP, with the command and its output noted.
