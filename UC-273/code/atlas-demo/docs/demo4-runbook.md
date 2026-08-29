# Demo 4 runbook — Repository Security & CI/CD Governance

This demo opens a deliberately-bad pull request and watches the security pipeline catch it before and after deployment. The bad changes live on the **`demo/bad-pr`** branch; `main` is clean.

```bash
# Automatically discover the active Project ID and Cloud Run Service URL
export PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
export URL=$(terraform -chdir=terraform output -raw service_url 2>/dev/null \
  || gcloud run services describe atlas-agent --region=us-central1 --format='value(status.url)' 2>/dev/null \
  || echo "http://localhost:8080")

echo "Project: $PROJECT_ID | Service URL: $URL"
```

---

## 1. Key Code Walkthrough (What to show the audience)

To show *how* CI/CD governance and shift-left agent security are implemented:

### A. Automated AI Code Reviewer (`.github/workflows/gemini-review.yml:L1-37`)
* **File:** [`.github/workflows/gemini-review.yml`](../.github/workflows/gemini-review.yml#L1-L37)
* **How it works:** Triggers on pull requests, using Gemini CLI to inspect diffs specifically for agent security anti-patterns:
```yaml
# .github/workflows/gemini-review.yml:24-36
- name: Gemini code review
  uses: google-github-actions/run-gemini-cli@v0
  with:
    gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
    prompt: |
      You are a security reviewer for an autonomous-agent codebase.
      Review the diff in this pull request and flag, with file and line:
        1. Hardcoded secrets or API keys (recommend Secret Manager).
        2. IaC misconfigurations (e.g. firewall rules allowing 0.0.0.0/0).
        3. Missing authorization / identity checks on tool calls.
```

### B. Vulnerable Code on PR Branch (`demo/bad-pr`)
* **Hardcoded API Key (`app/billing.py:L42`):**
  - Hardcodes a placeholder API key string `AIzaSyD...` in application code instead of referencing Secret Manager.
* **Overly Permissive Ingress (`terraform/insecure_debug.tf:L1-12`):**
  - Opens firewall rule `0.0.0.0/0` on ingress ports.
* **Unattested Container Image (`cloudbuild.yaml`):**
  - Replaces the signed build pipeline with an unverified public container image.

---

## 2. Google Cloud Console Walkthrough (What to show in the GCP Console)

1. **Security Command Center (SCC) Findings:**
   - **Navigation:** Navigate to **Security** > **Security Command Center** > **Findings**.
   - **What to show:**
     - High-severity finding: **Open Firewall Port (0.0.0.0/0)**
     - Finding: **Exposed Credential / API Key**
     - Toxic combination: Publicly exposed compute instance possessing unrotated credentials.

2. **Binary Authorization (Container Admission Policy):**
   - **Navigation:** Navigate to **Security** > **Binary Authorization**.
   - **What to show:** Show the default admission rule requiring **Attestors** (Cloud Build signed provenance). Unsigned images from public registries are automatically blocked from running on Cloud Run or GKE.

3. **Policy Controller (Policy-as-Code):**
   - **Navigation:** Navigate to **Anthos / GKE** > **Policy Controller** (or Policy-as-Code scanner in Cloud Build).
   - **What to show:** Active ConstraintTemplates (`K8sNoExternalIPs`, `GCPFirewallNoAllIngress`) blocking deployment of non-compliant infrastructure.

4. **Secret Manager (Remediation):**
   - **Navigation:** Navigate to **Security** > **Secret Manager**.
   - **What to show:** Show `atlas_api_key` where secrets are stored securely and injected at runtime via IAM.

---

## 3. Run It on Stage

```bash
# On stage: Open the PR against main
gh pr create --base main --head demo/bad-pr \
  --title "Add billing integration + debug access" \
  --body "Speeds up local testing. Adds billing tool, opens debug port, quick deploy."
```

### What happens in real-time:
1. **Gemini Review Comment:** Lands inline on `billing.py:42` — *"Hardcoded API key detected. Move to Google Secret Manager (`google_secret_manager_secret`)."*
2. **Policy-as-Code Check:** Fails the PR on `insecure_debug.tf` due to the `0.0.0.0/0` CIDR rule.
3. **Binary Authorization (Admission Gate):** Blocks deployment of the unattested image.
4. **Remediation:** Apply the fix (remove hardcoded key, drop firewall rule, restore verified container build) → All CI checks turn green.

---

## 4. Speaker Talk Track

> *"Security for autonomous agents begins long before runtime. Because agents can write code, modify infrastructure, and integrate external APIs, we must govern the development lifecycle.
>
> 1. In this PR (`demo/bad-pr`), a developer attempts to add a billing tool with a hardcoded key and open a debug firewall.
> 2. **Gemini Code Review** immediately catches the hardcoded key inline, preventing the secret from merging to `main`.
> 3. **Policy Controller** rejects the open `0.0.0.0/0` rule at the IaC stage.
> 4. **Binary Authorization** ensures that only container images cryptographically signed by our Cloud Build pipeline can ever be admitted to production.
> 5. If any toxic combination slips through, **Security Command Center** alerts the SOC immediately."*

---

## 5. Security Matrix

| Component | Stage | Threat Addressed | Enforcement Mechanism |
|---|---|---|---|
| **Gemini PR Review** | Pre-Merge | Hardcoded secrets & insecure tools | Inline PR review & status check |
| **Policy Controller** | Pre-Deploy | Insecure IaC & open firewalls | Policy-as-Code admission rules |
| **Binary Authorization** | Deployment | Unverified / Tampered container images | Digital signature attestation gate |
| **Security Command Center** | Post-Deploy | Misconfigurations & toxic combinations | Real-time cloud threat detection |

