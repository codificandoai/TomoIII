# Demo 4 — Policy Controller (OPA Gatekeeper) via GKE Hub / Fleet.
# Enforces Policy-as-Code (e.g. "no firewall may allow 0.0.0.0/0") on the cluster.
# Requires the GKE cluster from gke_sandbox.tf, so it is gated on both toggles.

locals {
  policy_controller_on = var.enable_policy_controller && var.enable_gke_sandbox
}

resource "google_gke_hub_membership" "atlas" {
  count         = local.policy_controller_on ? 1 : 0
  membership_id = "atlas-sandbox"

  endpoint {
    gke_cluster {
      resource_link = "//container.googleapis.com/${google_container_cluster.atlas[0].id}"
    }
  }

  depends_on = [google_project_service.guardrails]
}

resource "google_gke_hub_feature" "policycontroller" {
  count    = local.policy_controller_on ? 1 : 0
  name     = "policycontroller"
  location = "global"

  depends_on = [google_project_service.guardrails]
}

resource "google_gke_hub_feature_membership" "policycontroller" {
  count      = local.policy_controller_on ? 1 : 0
  location   = "global"
  feature    = google_gke_hub_feature.policycontroller[0].name
  membership = google_gke_hub_membership.atlas[0].membership_id

  policycontroller {
    policy_controller_hub_config {
      install_spec = "INSTALL_SPEC_ENABLED"

      policy_content {
        # Ship the reference constraint-template library so demo constraints have templates.
        template_library {
          installation = "ALL"
        }
      }

      # Turn plain audit into blocking enforcement.
      referential_rules_enabled = true
      audit_interval_seconds    = 60
    }
  }
}
