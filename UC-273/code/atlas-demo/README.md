# Atlas — Agent Security Demo App

The single application hardened across all four demos in **“Securing Autonomous AI Agents on
Google Cloud.”** Atlas is an autonomous financial-ops agent with four deliberately vulnerable
surfaces. Every guardrail is a flag you can flip **per request** from the console, so each demo is
a clean *attack (off) → defended (on)* toggle on one running Cloud Run revision — no redeploy.

## What it demonstrates

| Demo | Surface | Attack | Guardrails (toggle on) |
|---|---|---|---|
| 1 · Prompt hardening & authz | Support inbox (`/api/inbox/process`) | Indirect prompt injection in `msg-82` → exfiltrate account 4471 (BOLA) | Model Armor · ShieldGemma · DLP redaction · BOLA guard |
| 2 · Isolation & egress | Code interpreter (`/api/code/run`) | Generated code hits the metadata server & exfiltrates the token | Egress policy (allowlist) — plus VPC-SC/gVisor at the infra layer |
| 3 · Identity & gateway | Finance tool-server (`/api/finance/transfer`) | Rogue agent calls finance with no/wrong identity | Agent identity check — Agent Gateway mTLS/IAM at the infra layer |
| 4 · Repo & CI/CD | `.github/workflows/gemini-review.yml`, `cloudbuild.yaml` | Bad PR (secret + open firewall + unsigned image) | Gemini CLI review · Policy-as-Code · Binary Authz · SCC |

> The app enforces the **application-layer** guardrails (Model Armor call, DLP, BOLA, egress
> allowlist, identity). The **infrastructure** guardrails from the session — gVisor sandbox,
> VPC Service Controls, Agent Gateway mTLS/IAM, Binary Authorization — wrap the same app and are
> where Demos 2–4 get their strongest “blocked” moments. See the demo plan for that mapping.

## Reliability by design

- **Deterministic by default** (`ENABLE_LLM=false`): the planner reproduces the hijacked plan
  from the injected email without a live model call — so the stage demo never depends on a model
  round-trip. Set `ENABLE_LLM=true` to use the live Gemini planner on the Gemini Enterprise Agent
  Platform.
- **Live-or-fallback guardrails**: Model Armor uses the configured template when set, otherwise a
  heuristic detector. Either way the transcript labels the source.
- **No RCE in our image**: the code-interpreter demo *simulates* the payload by making the two real
  outbound calls (metadata + canary) a token-stealer would make — real egress behaviour, no
  arbitrary code execution inside Atlas.

## Run locally

```bash
cp .env.example .env          # edit project id if you want the live paths
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
# open http://localhost:8080
```

## Deploy to Cloud Run (Terraform)

```bash
# 1. Set up state/vars
cd terraform
cp terraform.tfvars.example terraform.tfvars   # edit project_id, region
terraform init
terraform apply                                # creates repo, SA, APIs, Cloud Run service

# 2. Build & push the image to the repo Terraform created
cd ..
gcloud auth configure-docker $(terraform -chdir=terraform output -raw artifact_registry_repo | cut -d/ -f1)
docker build -t $(terraform -chdir=terraform output -raw image) .
docker push $(terraform -chdir=terraform output -raw image)

# 3. Roll the service onto the new image (first apply used a placeholder tag)
terraform -chdir=terraform apply

echo "Console: $(terraform -chdir=terraform output -raw service_url)"
```

One-shot alternative (build + push + deploy) once the repo exists:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_REPO=atlas,_SERVICE=atlas-agent
```

## API quick reference

Every endpoint accepts a `guardrails` object to override the deployed defaults for that call.

```bash
# Demo 1 — baseline attack (guards off): watch the PII leak into the outbox
curl -sX POST $URL/api/inbox/process -H 'content-type: application/json' \
  -d '{"message_id":"msg-82","guardrails":{}}'

# Demo 1 — defended: injection blocked / BOLA denied / PII redacted
curl -sX POST $URL/api/inbox/process -H 'content-type: application/json' \
  -d '{"message_id":"msg-82","guardrails":{"enable_model_armor":true,"enable_bola_guard":true,"enable_dlp_redaction":true}}'

# Demo 2 — egress locked
curl -sX POST $URL/api/code/run -H 'content-type: application/json' \
  -d '{"task":"summarize","guardrails":{"enable_egress_policy":true}}'

# Demo 3 — rogue identity denied
curl -sX POST $URL/api/finance/transfer -H 'content-type: application/json' \
  -d '{"identity":null,"guardrails":{"enable_agent_identity":true}}'
```

## Layout

```
app/            FastAPI service (agent loop, tools, guardrails, console UI)
terraform/      Cloud Run + Artifact Registry + IAM + API enablement
cloudbuild.yaml Build/push/deploy pipeline (Demo 4)
.github/        Gemini CLI PR review workflow (Demo 4)
```
