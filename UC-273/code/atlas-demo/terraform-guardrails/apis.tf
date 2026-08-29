# APIs needed by the infra-layer guardrails.
locals {
  guardrail_services = [
    "compute.googleapis.com",
    "container.googleapis.com",             # GKE (Demo 2 sandbox)
    "accesscontextmanager.googleapis.com",  # VPC-SC (Demo 2)
    "binaryauthorization.googleapis.com",   # Demo 4
    "containeranalysis.googleapis.com",     # attestor notes (Demo 4)
    "gkehub.googleapis.com",                # Policy Controller (Demo 4)
    "anthosconfigmanagement.googleapis.com",
    "secretmanager.googleapis.com",         # Demo 4 remediation
    "artifactregistry.googleapis.com",
  ]
}

resource "google_project_service" "guardrails" {
  for_each                   = toset(local.guardrail_services)
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}
