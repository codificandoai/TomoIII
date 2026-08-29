# Demo 2 — VPC Service Controls perimeter.
# This is ORG-LEVEL: it needs an organization and an Access Context Manager policy, and the
# caller needs org-level permissions. Gated behind enable_vpc_sc so a plain project apply
# still works. The perimeter stops exfiltration of data from restricted services even if a
# token leaks — a request to the API from outside the perimeter is denied.

resource "google_access_context_manager_service_perimeter" "atlas" {
  count = var.enable_vpc_sc ? 1 : 0

  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/servicePerimeters/atlas"
  title  = "atlas-perimeter"

  status {
    resources = ["projects/${var.project_number}"]

    restricted_services = [
      "aiplatform.googleapis.com",
      "modelarmor.googleapis.com",
      "storage.googleapis.com",
      "secretmanager.googleapis.com",
    ]

    vpc_accessible_services {
      enable_restriction = true
      allowed_services = [
        "aiplatform.googleapis.com",
        "modelarmor.googleapis.com",
        "storage.googleapis.com",
        "secretmanager.googleapis.com",
      ]
    }
  }

  lifecycle {
    # Manage perimeter resources here; ignore drift from console edits during a live demo.
    ignore_changes = [status[0].resources]
  }
}
