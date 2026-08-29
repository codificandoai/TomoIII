"""Tools Atlas can call, plus the outbox that records anything the agent tries to send.

These are deliberately the vulnerable surfaces the demos exploit:
  * get_account  -> BOLA (Demo 1)
  * send_email   -> data exfiltration sink, DLP + egress checks (Demo 1 / 2)
  * run_code     -> untrusted code execution reaching metadata/egress (Demo 2)
  * finance_transfer -> privileged action gated by agent identity (Demo 3)
"""

from __future__ import annotations

from .config import Guardrails, settings
from . import data, guardrails


# Anything the agent "sends" lands here so the UI can show what would have leaked.
OUTBOX: list[dict] = []


class ToolDenied(Exception):
    def __init__(self, label: str, detail: str):
        super().__init__(detail)
        self.label = label
        self.detail = detail


def get_account(account_id: str, principal: str, g: Guardrails) -> dict:
    account = data.ACCOUNTS.get(account_id)
    if account is None:
        raise ToolDenied("not_found", f"account {account_id} does not exist")
    if g.enable_bola_guard and not guardrails.bola_authorized(principal, account):
        raise ToolDenied(
            "bola_denied",
            f"principal {principal} is not the owner of account {account_id}",
        )
    return account


def send_email(to: str, body: str, g: Guardrails) -> dict:
    steps: list[str] = []
    outgoing = body

    if g.enable_dlp_redaction:
        outgoing, found = guardrails.redact_pii(outgoing)
        steps.append(
            f"DLP redaction removed: {', '.join(found)}" if found else "DLP: nothing to redact"
        )

    host = to.split("@")[-1] if "@" in to else to
    if g.enable_egress_policy and not guardrails.egress_allowed(host):
        raise ToolDenied(
            "egress_denied",
            f"destination {host!r} not in allowed egress hosts {settings.allowed_egress_hosts}",
        )

    record = {"to": to, "body": outgoing, "steps": steps}
    OUTBOX.append(record)
    return record


def _find_sandbox_bin() -> str | None:
    import os
    import shutil
    for path in ["sandbox", "/bin/sandbox", "/usr/bin/sandbox", "/usr/local/bin/sandbox", "/google/bin/sandbox", "/google/sandbox/bin/sandbox"]:
        found = shutil.which(path) or (path if os.path.exists(path) else None)
        if found:
            return found
    return None


def _run_in_sandbox(urls: list[str], allow_egress: bool) -> list[dict] | None:
    """Execute real Python code inside Cloud Run Sandbox supervisor if available."""
    import json
    import subprocess

    sandbox_bin = _find_sandbox_bin()
    if not sandbox_bin:
        return None

    # Python script executed inside the sandbox enclave
    probe_script = f"""
import json, urllib.request, urllib.error
urls = {json.dumps(urls)}
results = []
for url in urls:
    try:
        req = urllib.request.Request(url, headers={{"Metadata-Flavor": "Google"}})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            results.append({{"url": url, "reached": True, "status": resp.getcode(), "sandbox": "gvisor-enclave"}})
    except urllib.error.HTTPError as e:
        results.append({{"url": url, "reached": True, "status": e.code, "sandbox": "gvisor-enclave"}})
    except urllib.error.URLError as e:
        results.append({{"url": url, "reached": False, "error": f"SandboxEgressBlocked ({{e.reason}})", "sandbox": "gvisor-enclave"}})
    except Exception as e:
        results.append({{"url": url, "reached": False, "error": f"SandboxEgressBlocked ({{type(e).__name__}}: {{e}})", "sandbox": "gvisor-enclave"}})
print(json.dumps(results))
"""
    import sys
    cmd = [sandbox_bin, "do"]
    if allow_egress:
        cmd.append("--allow-egress")
    cmd.extend(["--", sys.executable, "-c", probe_script])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        lines = output.strip().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                return json.loads(line)
        if proc.returncode != 0:
            print(f"[sandbox error] returncode={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}", flush=True)
    except Exception as exc:
        print(f"[sandbox exception] {exc}", flush=True)
    return None


def run_code(task: str, g: Guardrails) -> dict:
    """Execute code interpreter task with true Cloud Run Sandbox infrastructure containment."""
    target_urls = [settings.metadata_url, settings.exfil_canary_url]
    observations = []

    if g.enable_egress_policy:
        # True infrastructure containment: execute in Cloud Run Sandbox enclave without egress
        sandbox_results = _run_in_sandbox(target_urls, allow_egress=False)
        if sandbox_results is not None:
            observations = sandbox_results
        else:
            for url in target_urls:
                host = url.split("/")[2]
                observations.append(
                    {"url": url, "reached": False, "error": "EgressPolicyDenied", "host": host}
                )
    else:
        # Attack path: unsandboxed tool execution where runtime SA token and egress are accessible
        for url in target_urls:
            observations.append(guardrails.probe_egress(url))

    token_stolen = any(o.get("reached") and "metadata" in o["url"] for o in observations)
    exfiltrated = any(o.get("reached") and "steal" in o["url"] for o in observations)
    return {
        "task": task,
        "observations": observations,
        "token_stolen": token_stolen,
        "exfiltrated": exfiltrated,
    }


def finance_transfer(
    amount_usd: float,
    to_account: str,
    presented_identity: str | None,
    g: Guardrails,
    token: str | None = None,
) -> dict:
    if g.enable_agent_identity:
        verification = guardrails.verify_agent_token(
            token, presented_identity=presented_identity
        )
        if not verification["valid"]:
            raise ToolDenied(
                verification["label"],
                verification["detail"],
            )
        return {
            "status": "ok",
            "amount_usd": amount_usd,
            "to_account": to_account,
            "verification": verification,
        }
    return {
        "status": "ok",
        "amount_usd": amount_usd,
        "to_account": to_account,
        "verification": {
            "crypto_status": "BYPASSED",
            "detail": "Agent Gateway identity enforcement disabled (baseline attack path)",
        },
    }
