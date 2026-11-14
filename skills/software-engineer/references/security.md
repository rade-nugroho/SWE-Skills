# Security (secure engineering)

How to build things safely: the choices to make in design and the checks to run on your own diff. Not an attack guide.

## Contents
1. Secure-design principles
2. Authentication vs authorization
3. Data protection: TLS, encryption, keys, secrets
4. Input handling and common web risks
5. Dependencies and supply chain
6. Logging and monitoring
7. Secure SDLC by phase
8. Backup and disaster recovery
9. Security review checklist for your diff

Related: `ci-cd.md` (pipeline scanning), `networking.md`, `api-gateway-queues-rate-limits.md` (rate limiting, login throttling), `distributed-systems.md` (node-to-node trust), `availability-and-consistency.md`, `fault-tolerance.md`, `quality-and-process.md`.

## 1. Secure-design principles

| Principle | Consequence in code or design |
|---|---|
| Least privilege | DB user for the app can't `DROP`; service tokens carry only needed scopes; cloud roles list actions, not `*`. |
| Defense in depth | Don't rely on one control: validate at the edge and again in the domain layer; authz in the handler and the query. |
| Fail closed | On error, timeout, or missing policy, deny. `try: allowed = check() except: allowed = False`, never the reverse. |
| Secure defaults | New endpoints require auth unless explicitly marked public; new flags, buckets, and users start private/off. |
| Minimize attack surface | Delete unused endpoints, debug routes, ports, dependencies, and admin UIs; expose only what a requirement needs. |
| Never trust input | Everything crossing a boundary (HTTP, queue, file, env, another service, an LLM output) is parsed and validated. |
| Separation of duties | The person or pipeline that writes code isn't the only one who can ship it; deploy keys differ from dev keys; one role can't both create and approve payments. |
| Plan for failure | Assume a breach or outage will happen: logs to detect it, backups to recover, limited blast radius. |

When a design doc has a "security" line, make it concrete: who can call this, what data it touches, what happens when a check fails.

## 2. Authentication vs authorization

| | Authentication (authn) | Authorization (authz) |
|---|---|---|
| Question | Who are you? | What may you do? |
| Happens | First | After identity is known |
| Mechanisms | Password, MFA, passkeys, SSO, API key, client cert | Roles, attribute policies, ACLs, scopes |
| Failure response | 401 | 403 (or 404 to hide existence) |
| Typical bug | Weak reset flow, no throttling | Missing check on one endpoint or object |

### Practical choices

| Choice | Guidance |
|---|---|
| Session cookie vs token | Browser app on one domain: server session or signed cookie with `HttpOnly; Secure; SameSite=Lax/Strict`. APIs, mobile, service-to-service: bearer tokens. Don't keep tokens in `localStorage` if XSS is a concern. |
| JWT | A signed, self-contained claim set. Pin the allowed algorithm, verify signature, `exp`, `aud`, `iss`. Keep lifetimes short; revocation is hard, so pair with refresh tokens you can revoke. Don't put secrets in the payload (it is only encoded). |
| OAuth2 | Delegated authorization: an app gets a scoped access token without the user's password. Use authorization code + PKCE for user flows. |
| OIDC | Identity layer on OAuth2 (ID token says who logged in). Prefer an established provider over rolling your own login. |
| Password storage | Slow, salted, adaptive hash: argon2id first choice; bcrypt or scrypt acceptable. Never plain, never fast hashes (MD5/SHA-256 alone), never reversible encryption. Compare in constant time; use library defaults for cost and salt. |
| MFA | Offer or require for admins and sensitive actions; prefer passkeys/WebAuthn or TOTP over SMS. Protect recovery flows as strongly as login. |
| Login abuse | Rate-limit and lock out progressively; same error for "no user" and "wrong password". |

### Authorization models

| Model | Use when | Note |
|---|---|---|
| RBAC | Few clear job functions (admin, editor, viewer) | Simple to audit; roles explode if rules depend on context. |
| ABAC | Rules depend on attributes: owner, tenant, department, time, data sensitivity | More expressive, harder to reason about; centralize the policy. |
| Ownership/ReBAC | "Owner or member of the project" | Common for per-object access. |

Rules:
- Enforce on the server for every request, never only in UI or client code. Hidden buttons are not security.
- Check the object, not just the role: `WHERE id = :id AND tenant_id = :caller_tenant`. Missing this is broken object-level authorization (the IDOR family): a user changes an ID in the URL and reads someone else's data.
- Derive the user and tenant from the verified session or token, not from request fields.
- Deny by default; write one tested helper (`require(user, action, resource)`) instead of ad hoc `if`s.
- Test the negative: user A gets 403/404 on user B's resource, for each endpoint.

## 3. Data protection

### In transit: TLS

SSL is obsolete (SSL 2.0/3.0 are broken and retired). "SSL certificate" is just habit for a TLS certificate. Use TLS 1.2 or 1.3; disable TLS 1.0/1.1.

| | SSL | TLS |
|---|---|---|
| Status | Obsolete, insecure | Current standard (IETF) |
| Versions | 2.0, 3.0 | 1.0, 1.1 (deprecated), 1.2, 1.3 |
| Crypto | Weak ciphers and MACs | Modern suites, forward secrecy; 1.3 allows only AEAD suites |
| Handshake | Slower, more round trips | 1.3 is shorter (1-RTT) |

- Terminate TLS everywhere users or other services connect; redirect HTTP to HTTPS and send `Strict-Transport-Security` (HSTS) once HTTPS is solid.
- Use certificates from a trusted CA (ACME/Let's Encrypt or internal CA), with automated renewal and an expiry alert. Verify certs and hostnames in clients; `verify=False` is a bug, not a dev convenience to commit.
- mTLS between services when each side must prove identity (internal APIs, service mesh). See `distributed-systems.md`.

### At rest and keys
- Encrypt databases, disks, and backups (provider-managed encryption is a fine default). Encrypt specific fields (e.g. national IDs) in the app when DB admins shouldn't read them.
- Use standard algorithms via vetted libraries (AES-256-GCM, ChaCha20-Poly1305). Never invent crypto or reuse a nonce.
- Keep keys in a KMS or HSM, separate from the data they protect; use envelope encryption (data keys wrapped by a master key). Rotate on a schedule and support re-encryption; restrict who can decrypt and log it.
- Collect and keep less: data you don't store can't leak. Mask or tokenise sensitive fields.

### Secrets
- Read from environment variables or a secret manager (Vault, cloud secrets); never from source, images, or committed `.env` files. Add secret scanning to pre-commit/CI.
- Never print secrets, tokens, or full auth headers in logs or error messages.
- Give each environment and service its own secret; least-privilege scopes.
- If a secret leaked (commit, log, screenshot): revoke and rotate first, then clean up history. Removing the commit doesn't un-leak it.

## 4. Input handling and common web risks

Validate on the server: type, length, range, format, allow-list of values. Reject, don't "fix up". Then apply the specific defense below; validation alone is not enough.

| Risk | What goes wrong | Standard fix |
|---|---|---|
| Injection (SQL, NoSQL, OS command, LDAP) | Input is parsed as code | Parameterized queries / ORM bindings; no string-built queries; avoid shell, else pass an argument array with no shell and allow-list args |
| XSS | Input rendered as script in a page | Output encoding for the context (HTML, attr, JS, URL); framework auto-escaping; avoid `innerHTML`; Content-Security-Policy; sanitize rich text with a vetted library |
| CSRF | Browser sends cookies on a forged request | Anti-CSRF tokens on state-changing requests; `SameSite` cookies; check `Origin`; no state change on GET |
| SSRF | Server fetches an attacker-chosen URL (internal services, cloud metadata) | Allow-list hosts/schemes; resolve and block private/link-local ranges; no redirects; network egress rules; metadata service hardening |
| Insecure deserialization | Untrusted bytes rebuild objects and run code | Use data-only formats (JSON) with schema validation; never `pickle`/native deserialize untrusted data; sign data if it must round-trip |
| Path traversal | `../` escapes the intended directory | Don't build paths from input; map ID to stored filename; canonicalize and check the result stays under the base dir |
| Mass assignment | Request body sets fields like `role` or `is_admin` | Explicit allow-listed DTO/fields per endpoint; never bind request straight to the model |
| Broken object-level authz | Changing an ID reaches others' data | See section 2: per-object check |
| Unrestricted upload | Executable or huge file stored/served | Check size, content type by sniffing, rename, store outside web root, serve with `Content-Disposition` and no execution |
| Open redirect | `?next=` sends users to a phishing site | Allow-list targets or accept only relative paths |

Also: set security headers (CSP, `X-Content-Type-Options`, frame restrictions), configure CORS to specific origins (not `*` with credentials), return generic errors to clients (details go to logs), and rate-limit expensive or abuse-prone endpoints (`api-gateway-queues-rate-limits.md`).

## 5. Dependencies and supply chain

- Commit lockfiles; install in CI from the lockfile (`npm ci`, `pip install --require-hashes`, `cargo --locked`). Pin versions; avoid `latest` and floating tags, including base images (pin by digest where practical).
- Run an audit (`npm audit`, `pip-audit`, `cargo audit`, Dependabot/Renovate, an SCA scanner) in CI and on a schedule; triage by exploitability and reachability.
- Before adding a dependency: is it needed, maintained, widely used, and is the name spelled right (typosquatting)? A few lines of code beats a new dependency.
- Keep third-party permissions narrow: scoped API keys, timeouts, and a plan for when the vendor is down.
- Pipeline hygiene: protect main, require review, keep CI secrets scoped, avoid piping remote scripts into a shell. See `ci-cd.md`.

## 6. Logging and monitoring

- Log security events with context: login success/failure, permission denials, privilege changes, token/key use, input-validation rejections, config changes. Include who, what, when, source, and a request/correlation ID.
- Don't log passwords, tokens, keys, full card or ID numbers, or personal data beyond what's needed; redact or hash at the logging layer. Beware logging whole request bodies or headers.
- Prevent log injection: encode or structure (JSON) user-supplied values so newlines can't forge entries.
- Send logs off-host to append-only storage; set retention that matches policy and privacy law.
- Alert on patterns (burst of failed logins, new admin, spikes in 403s) and keep a basic incident plan: detect, contain, remove, recover, review.

## 7. Secure SDLC by phase

| Phase | Security activity | What you do as the engineer |
|---|---|---|
| Requirements | Security and compliance requirements, data classification | Note what data is sensitive, who may access it, auth needs, retention, regulations; give NFRs numbers |
| Design | Threat modeling, secure architecture review | Draw trust boundaries; ask what can go wrong at each (spoofing, tampering, leaks, denial, privilege escalation); decide authn/authz, encryption, least privilege |
| Implementation | Secure coding, code review | Follow sections 2-6; use framework defaults; review diffs with the checklist below |
| Testing/CI | SAST, DAST, dependency and secret scanning, security tests | Add negative tests (unauthorized access, bad input); fix findings or record accepted risk; see `ci-cd.md` |
| Deployment | Hardening, secrets management, config review | Minimal images, no default creds, closed ports, IaC scanning, separate prod access, safe rollout and rollback |
| Operations | Patching, monitoring, incident response, periodic review | Update dependencies and OS on a cadence, watch alerts, rehearse the response, write post-incident fixes into backlog |

Find issues early: a missing authz rule caught in design review is cheaper than one found in production. Quality practices: `quality-and-process.md`.

## 8. Backup and disaster recovery

### Backup types

| Type | Copies | Backup cost | Restore |
|---|---|---|---|
| Full | Everything | Largest, slowest | Simplest: one set |
| Incremental | Changes since the last backup of any kind | Smallest, fastest | Slowest: full plus every increment in order |
| Differential | Changes since the last full | Grows until next full | Full plus the latest differential |

**3-2-1 rule:** at least 3 copies, on 2 different media or independent systems, with 1 off-site. Add an immutable or offline copy to survive ransomware or a compromised admin account. Encrypt backups and restrict who can delete them.

### RPO and RTO drive the design
- **RPO** (recovery point objective): how much data you can afford to lose, as time. Backup or replication interval must be shorter than RPO: RPO of 15 min means continuous replication or frequent log shipping, not nightly dumps.
- **RTO** (recovery time objective): how long the service may be down. RTO of minutes needs standby capacity already running; RTO of a day allows rebuilding from backup.
- Set both per system with the business, write them in the design doc, and pick the cheapest strategy that meets them.

### DR strategies (cost rises as recovery time falls)

| Strategy | What runs in the DR site | Typical RTO / RPO | Cost |
|---|---|---|---|
| Backup and restore | Nothing; restore backups and rebuild | Hours to days / up to last backup | Lowest |
| Pilot light | Data replicated; core pieces (DB) on, app tier off until needed | Tens of minutes to hours | Low |
| Warm standby | Scaled-down full copy always running | Minutes | Medium |
| Multi-site active-active | Full capacity in several sites serving traffic | Near zero | Highest; adds data-consistency complexity (`availability-and-consistency.md`) |

Plan failover (switch to standby) and failback (return to primary), keep infrastructure as code so environments are reproducible, and see `fault-tolerance.md` for in-service resilience.

### Test restores
A backup never restored is a hope. Schedule restore drills (automated where possible), verify integrity and application-level correctness, measure actual time against RTO, keep the runbook current, and alert when a backup job fails or shrinks suddenly.

## 9. Security review checklist for your diff

Run this on your own change before reporting; note anything skipped.

**Access**
- [ ] Every new or changed endpoint/handler requires authentication unless deliberately public
- [ ] Authorization checked server-side on each request and each object (tenant/owner), deny by default
- [ ] Identity and tenant come from the session/token, not request fields
- [ ] Negative test: another user's resource is refused

**Input and output**
- [ ] Input validated (type, size, format, allow-list) at the boundary
- [ ] Queries parameterized; no shell, eval, or path built from input
- [ ] Output encoded; no raw HTML from user data; CSRF protection on cookie-authenticated writes
- [ ] Request bodies bound to explicit fields (no mass assignment)
- [ ] Outbound fetches of user-supplied URLs are allow-listed (SSRF)
- [ ] Errors to clients are generic; details only in logs

**Data and secrets**
- [ ] No secrets, keys, or tokens in code, tests, fixtures, config, or logs
- [ ] Sensitive data encrypted in transit (TLS) and at rest; passwords use argon2id/bcrypt/scrypt
- [ ] Only needed personal data collected, stored, and logged
- [ ] Cookies `HttpOnly`, `Secure`, `SameSite`; tokens short-lived and fully verified

**Dependencies and config**
- [ ] New dependencies justified, pinned, lockfile updated, audit clean or findings noted
- [ ] No debug flags, default credentials, wildcard CORS, or disabled TLS verification left in
- [ ] Failures deny rather than allow (fail closed)

**Operations**
- [ ] Security-relevant events logged without sensitive values; rate limits on abuse-prone paths
- [ ] New data store has backup, retention, and restore plan consistent with RPO/RTO

In the report, state what you checked, what you could not (e.g. no DAST run), and any accepted risk.
