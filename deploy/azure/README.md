# Azure deployment (Container Apps) — and the provider-swap boundary

Azure is the **first** deployment target (docs/07 Phase 2, W4). It is not a
lock-in. Everything Azure-specific is confined to **this directory**; the
application image knows nothing about Azure.

## The provider-swap boundary

| Layer | Azure-aware? | Where |
|---|---|---|
| Application code | **No** | `src/mre/**` — reads only `MRE_*` config, no cloud SDK |
| Container image | **No** | `Dockerfile` (root) — provider-agnostic, runs anywhere |
| Local parity stack | **No** | `docker-compose*.yml`, `deploy/local-tls/` — Docker/Caddy |
| Cloud deployment | **Yes** | `deploy/azure/` — `main.bicep`, `deploy.sh`, `.env` |

To move to another provider (AWS App Runner / ECS, GCP Cloud Run, a bare VM,
Kubernetes), you write a **sibling directory** (`deploy/aws/`, `deploy/gcp/`, …)
that provides the same four things and touch **nothing outside it**:

1. **Managed TLS ingress** → forwards HTTPS to the container's plaintext `:8000`
   (the cloud equivalent of the local Caddy proxy).
2. **A persistent, encrypted volume** mounted at `/data` (`MRE_DATA_ROOT`) —
   registry + snapshots + evidence. Azure: Azure Files on an encrypted storage
   account. Encryption at rest is a storage-layer property (docs/08 §2).
3. **Secret injection** for any credentials (today the optional
   `ANTHROPIC_API_KEY`) as environment variables from the platform secret store
   — never baked into the image (docs/08 §3).
4. **A single replica** (single tenant by construction, docs/08 §4): one writer
   for the SQLite registry and the file volume.

## What `main.bicep` provisions

- An **encrypted** Storage account + file share backing the `/data` volume.
- A Container Apps managed environment with that share linked as storage.
- The API container app: external managed-TLS ingress on `:8000`, ACR pull
  creds and the optional Anthropic key as **secrets**, `/health` liveness &
  readiness probes, `MRE_DATA_ROOT=/data`, `PYTHONHASHSEED=0`, pinned to one
  replica.

## Deploy

```bash
cp deploy/azure/.env.example deploy/azure/.env   # fill in RESOURCE_GROUP, ACR_NAME
az login
deploy/azure/deploy.sh                            # ACR build -> bicep deploy
python deploy/smoke.py --base-url https://<fqdn>  # exit demo over the API
```

`deploy.sh` builds the image with `az acr build --target runtime` (the shipped
stage), so the cloud image is the same multi-stage build CI tests.

## Verification status (honest)

Written and shipped this session; **not deployed to a live Azure subscription**
(none available in-session). The Bicep is unvalidated against ARM, and the
smoke script has been exercised only against the local stack (see the session
close in `docs/04`). `deploy-verified-locally` is not `deploy-verified-in-cloud`
— the first live `az deployment group create` + cloud smoke run is the
outstanding confirmation.
