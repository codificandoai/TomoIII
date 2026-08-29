# Demo 2 runbook — Tool Isolation & Cloud Run Sandbox Enclaves

Atlas's code-interpreter tool runs model-generated Python. A poisoned task causes untrusted code execution to reach the GCE **metadata server** (`169.254.169.254`) to steal the runtime's service-account OAuth token, then **exfiltrate** it to an external destination. You demonstrate the attack succeeding with guards off (unsandboxed), then toggle the egress policy on to execute inside the **Cloud Run Sandbox supervisor** (`sandbox do`), proving kernel-level process and network containment.

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

To show *how* runtime sandboxing is implemented in the codebase:

### A. Sandbox Supervisor Discovery (`app/tools.py:L61-68`)
* **File:** [`app/tools.py`](../app/tools.py#L61-L68)
* **How it works:** Detects the Google Cloud Run Sandbox supervisor binary (`sandbox`) provided in the container environment:
```python
# app/tools.py:61-68
def _find_sandbox_bin() -> str | None:
    for path in ["sandbox", "/bin/sandbox", "/usr/bin/sandbox", "/usr/local/bin/sandbox", "/google/bin/sandbox"]:
        found = shutil.which(path) or (path if os.path.exists(path) else None)
        if found:
            return found
    return None
```

### B. Untrusted Code Spawning in gVisor Enclave (`app/tools.py:L71-116`)
* **File:** [`app/tools.py`](../app/tools.py#L71-L116)
* **How it works:** Spawns a dedicated subprocess inside the gVisor sandbox enclave via `sandbox do -- [sys.executable, -c, probe_script]`, intercepting socket calls at the sandbox kernel boundary:
```python
# app/tools.py:99-105
cmd = [sandbox_bin, "do"]
if allow_egress:
    cmd.append("--allow-egress")
cmd.extend(["--", sys.executable, "-c", probe_script])
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
```

### C. Tool Dispatch Logic (`app/tools.py:L119-148`)
* **File:** [`app/tools.py`](../app/tools.py#L119-L148)
* **How it works:** When `enable_egress_policy: true`, untrusted code is locked in the sandbox without egress (`allow_egress=False`). When false (the baseline attack), the code runs unsandboxed on the host network.

---

## 2. Google Cloud Console Walkthrough (What to show in the GCP Console)

1. **Cloud Run Container Sandbox Configuration:**
   - **Navigation:** Navigate to **Cloud Run** > **atlas-agent** > **Revisions** tab > Click active revision.
   - **What to show:**
     - **Execution Environment:** `Second Generation` / Cloud Run Container Sandbox enabled.
     - **Container resources:** Dedicated CPU/memory limits allocated per sandbox container.

2. **Cloud Logging (Kernel Socket Drops):**
   - **Navigation:** Navigate to **Logging** > **Logs Explorer**.
   - **Query:**
     ```text
     resource.type="cloud_run_revision"
     resource.labels.service_name="atlas-agent"
     "SandboxEgressBlocked"
     ```
   - **What to show:** Highlight the live gVisor network layer rejection:
     - `[Errno 101] Network is unreachable` (Link-local metadata IP `169.254.169.254`)
     - `[Errno -3] Temporary failure in name resolution` (External exfiltration destination)

3. **VPC Network & Firewall Policies (Defense-in-Depth):**
   - **Navigation:** Navigate to **VPC network** > **Firewall policies**.
   - **What to show:** Default-deny egress firewall rules preventing container instances from routing to unapproved external CIDRs.

---

## 3. The attack (unsandboxed / egress open)

In the Atlas console (`/`), click **Run attack (egress open)** on Demo 2, or run via `curl`:

```bash
curl -sX POST "$URL/api/code/run" \
  -H 'content-type: application/json' \
  -d '{"task":"summarize yesterday","guardrails":{}}' | jq
```

### Response (Credential stolen & exfiltrated):
```json
{
  "task": "summarize yesterday",
  "outcome": "exfiltrated",
  "token_stolen": true,
  "exfiltrated": true,
  "guardrails": {
    "enable_egress_policy": false
  },
  "observations": [
    {
      "url": "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
      "reached": true,
      "status": 200
    },
    {
      "url": "https://example.com/steal",
      "reached": true,
      "status": 404
    }
  ]
}
```

Console transcript:
```
outcome: EXFILTRATED
  REACHED http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token [200]
  REACHED https://example.com/steal [404]
  token_stolen: true · exfiltrated: true
```

---

## 4. The defense — Cloud Run Sandbox Enclave

In the Atlas console, click **Run defended (egress locked)** on Demo 2, or run via `curl`:

```bash
curl -sX POST "$URL/api/code/run" \
  -H 'content-type: application/json' \
  -d '{"task":"summarize yesterday","guardrails":{"enable_egress_policy":true}}' | jq
```

### Response (Contained at kernel boundary):
```json
{
  "task": "summarize yesterday",
  "outcome": "contained",
  "token_stolen": false,
  "exfiltrated": false,
  "guardrails": {
    "enable_egress_policy": true
  },
  "observations": [
    {
      "url": "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
      "reached": false,
      "error": "SandboxEgressBlocked ([Errno 101] Network is unreachable)",
      "sandbox": "gvisor-enclave"
    },
    {
      "url": "https://example.com/steal",
      "reached": false,
      "error": "SandboxEgressBlocked ([Errno -3] Temporary failure in name resolution)",
      "sandbox": "gvisor-enclave"
    }
  ]
}
```

Console transcript:
```
outcome: CONTAINED
  blocked http://metadata.google.internal/.../token (SandboxEgressBlocked ([Errno 101] Network is unreachable))
  blocked https://example.com/steal (SandboxEgressBlocked ([Errno -3] Temporary failure in name resolution))
  token_stolen: false · exfiltrated: false
```

---

## 5. Under the Hood: Execution Comparison

| Mode | Execution Environment | Network Egress | Metadata Access (`169.254.169.254`) | Result |
|---|---|---|---|---|
| **Attack (Guards Off)** | Unsandboxed Python process | Allowed (Host network) | Reached (`200 OK` SA token stolen) | `EXFILTRATED` |
| **Defended (Guards On)** | **Cloud Run Sandbox Enclave (`sandbox do`)** | Blocked (`Errno -3` Name resolution failure) | Blocked (`Errno 101` Network unreachable) | `CONTAINED` |

---

## 6. Speaker Talk Track

> *"When an agent executes code generated by an LLM, we cannot trust that code with direct access to the container environment or network.
>
> 1. In the baseline run, the untrusted script reaches the link-local metadata server, extracts the service account's OAuth token, and phones home to an exfiltration endpoint.
> 2. With the defense enabled, the agent executes the code inside a **Cloud Run Sandbox supervisor enclave (`sandbox do`)** ([`app/tools.py:99`](../app/tools.py#L99)).
> 3. Under the hood, gVisor virtualizes system calls and drops outbound network sockets at the kernel level.
> 4. Notice that metadata access returns `[Errno 101] Network is unreachable` and external DNS returns `[Errno -3] Name resolution failure`. The attack is fully contained with zero extra infrastructure to manage."*


