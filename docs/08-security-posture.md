# Security Posture (W4 baseline)

**Document 8** · Status: v0.1 (session 2.4, first cloud deploy) · Companion to
docs/07 §5 W4. Scope: the encryption, secrets, and tenancy posture that ships
with the first cloud deployment. This is the *baseline*, not certification —
SOC 2 is post-window and trigger-gated (docs/07 §4.3).

This note states **what is encrypted and where, where keys live, and the
single-tenant-by-construction rule**. It is deliberately short and will grow as
the pilot and any prospect #2 sharpen the requirements.

---

## 1. Encryption in transit (TLS)

The API never terminates TLS itself; a **terminating reverse proxy sits in
front** and speaks plaintext to the API over a private network only.

| Environment | Terminator | Certificate / key |
|---|---|---|
| Local parity | Caddy (`docker-compose.tls.yml`, `deploy/local-tls/Caddyfile`) | Caddy's `tls internal` local CA — self-signed, offline, no ACME |
| Cloud (Azure-first) | The platform's managed TLS front end (deploy/azure) | Platform-managed certificate; auto-renewed by the platform |

The application is identical in both: it listens on plaintext `:8000` behind
the terminator, so a provider swap changes only the front end, never the image.
HSTS is set at the terminator in both environments.

## 2. Encryption at rest

All durable state lives under a single mount, `MRE_DATA_ROOT=/data`: the run
registry (`registry.sqlite`), submissions, snapshots, and the evidence store.
Encryption at rest is a **property of the volume's backing store, not of the
application** — the app writes ordinary files and is agnostic to the cipher.

| Environment | Backing store | Key custody |
|---|---|---|
| Local parity | The Docker named volume `mre-data` on a host-encrypted (e.g. LUKS/FileVault/BitLocker) disk | Host disk-encryption key — outside the repo and image |
| Cloud (Azure-first) | An encrypted managed disk backing the persistent volume | Platform-managed keys (KMS-class); customer-managed-key upgrade is a later decision |

There is no application-level field encryption in the baseline: the threat
model is disk/host compromise and backup theft, answered at the storage layer.
Application-level encryption of specific evidence fields is a post-baseline
option if a pilot/prospect requires it.

## 3. Secrets

**Environment injection only. Never in the image, never in the repo.**

- The image contains no credentials (verified: multi-stage build copies only a
  venv and app code; `docker history` shows no secret layers).
- Runtime secrets are injected as environment variables by the platform's
  secret store (Azure Key Vault-class) in the cloud, or a local `.env`/compose
  `environment` that is **git-ignored** in dev. The only such secret today is
  `ANTHROPIC_API_KEY` (the M10 explainer's optional LLM path; absent → the
  explainer runs without the LLM).
- Application configuration is provider-neutral `MRE_*` variables
  (`MRE_DATA_ROOT`); no provider-specific env-var names appear in application
  code, so the secret-store binding is a deploy concern (deploy/azure), not an
  app concern.
- **CI enforcement:** the `secret-scan` job (gitleaks, `.gitleaks.toml`) fails
  the build on any committed credential across the full git history.

## 4. Tenancy — single tenant by construction

The system is built for **one tenant (the pilot)**. This is an architectural
rule, not just a deployment fact:

- One `MRE_DATA_ROOT` per deployment holds exactly one customer's registry,
  snapshots, and evidence. There is no tenant key on any entity or evidence
  record, and no code path selects data by tenant — isolation is the process/
  volume boundary itself. A second customer means a **second, separate
  deployment** (its own image instance, its own encrypted volume, its own
  secrets), never a shared store.
- **Tenant-#2 isolation trigger.** The first time a *second* tenant must be
  served from shared infrastructure (rather than a second isolated deployment),
  multi-tenancy becomes a design item: a tenant identifier on the canonical
  snapshot and every evidence record, tenant-scoped registry queries, and
  per-tenant key custody. Until that trigger fires, adding a tenant column
  would be dead complexity, and the constitution's evidence rules assume a
  single canonical store. This is named here so the trigger is not discovered
  by accident.

## 5. Not in the baseline (named, deferred)

- **SOC 2 / formal attestation** — post-window, trigger-gated (pilot converts
  to paid, or prospect #2 requires attestation): Type I then Type II on its
  long evidence clock (docs/07 §4.3). Encryption now; attestation when commerce
  demands it.
- **Multi-tenant hardening** — on the tenant-#2 trigger (§4).
- **Customer-managed keys, application-level field encryption, audit-log
  export** — half-built by the evidence contract; hardened when a pilot/prospect
  requires them.
