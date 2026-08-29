# Atlas — Infrastructure-layer guardrails

The enforcement points that live *around* the Atlas app, behind Demos 2–4. Kept as a
separate root module because several resources are heavier or org-scoped (GKE, VPC Service
Controls) and you don't want them in the critical path of the simple app deploy.

Everything is **off by default** — enable one control per demo via `terraform.tfvars`.

## What maps to what

| File | Demo | Control |
|---|---|---|
| `network.tf` | 2 | VPC, subnet (private Google access), Cloud Router + NAT, route to restricted API VIP |
| `firewall.tf` | 2 | Deny-all egress + allowlist, scoped to the `atlas-locked` tag |
| `gke_sandbox.tf` | 2 | GKE cluster + **gVisor** node pool + **Workload Identity** (GKE_METADATA closes the token-theft path) |
| `vpc_sc.tf` | 2 | **VPC Service Controls** perimeter (org-level) |
| `binary_authorization.tf` | 4 | Attestor + **require-attestation** admission policy |
| `policy_controller.tf` | 4 | **Policy Controller** (OPA Gatekeeper) via GKE Hub |
| `secret_manager.tf` | 4 | The Secret Manager secret the hardcoded key should move to |

> **Demo 3 (Agent Gateway / identity)** is intentionally not here: Agent Gateway on the
> Gemini Enterprise Agent Platform is configured through its own API/console
> (Service Extensions, Agent Identity, IAM), and does not yet have first-class Terraform
> resources. This module provides the *foundation* it builds on — Workload Identity on the
> GKE cluster. Configure the gateway itself per the codelab after this applies.

## Apply order

```bash
cd terraform-guardrails
cp terraform.tfvars.example terraform.tfvars   # edit project_id, project_number, toggles
terraform init
terraform apply
```

Then, to bring the **running Cloud Run app** under the egress lockdown (Demo 2), pass the
network outputs into the app module:

```bash
NET=$(terraform -chdir=terraform-guardrails output -raw network)
SUBNET=$(terraform -chdir=terraform-guardrails output -raw subnet)
terraform -chdir=terraform apply -var="vpc_network=$NET" -var="vpc_subnet=$SUBNET"
```

## Notes & caveats

- **`terraform validate` was not run here** (no Terraform binary on the author's machine).
  Run `terraform init && terraform validate` in each module before applying.
- **VPC-SC is org-level.** `enable_vpc_sc` needs an organization, an Access Context Manager
  policy (`access_policy_id`), the project number, and org-level IAM. Leave it off for a
  project-only demo.
- **The metadata server can't be firewalled.** 169.254.169.254 is link-local; the real fix
  for the token-theft path is Workload Identity (`GKE_METADATA`), already set on the sandbox
  node pool.
- **Cost:** the GKE cluster and NAT bill while up. `terraform destroy` this module between
  rehearsals; the app module (Cloud Run, scale-to-zero) is cheap to leave running.
- **Firewall scope:** rules target the `atlas-locked` network tag so they don't disrupt the
  cluster control plane. Tag the code-interpreter workloads with it; for Cloud Run, direct
  VPC egress sends traffic through the same subnet and NAT.

## Policy Controller — the Demo 4 constraint

Policy Controller installs the templates; you still apply the constraint that blocks the
open firewall. After the feature is enabled, apply a Gatekeeper constraint, e.g.:

```yaml
# no-open-ingress.yaml — deny any resource that opens 0.0.0.0/0
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sBlockedNamespaces   # swap for the template that fits your target resource
metadata:
  name: atlas-no-world-open
spec:
  enforcementAction: deny
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Service"]
```

For **Terraform/IaC** scanning of the `0.0.0.0/0` firewall in the bad PR, pair this with a
CI check (e.g. Policy Controller's `terraform` gator, or a `gcloud`/OPA step in the pipeline)
so the misconfig is caught at PR time as well as at admission.
```
