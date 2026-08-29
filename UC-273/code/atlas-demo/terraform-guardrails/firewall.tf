# Demo 2 — egress lockdown.
# Rules target the network tag `atlas-locked`, so only the agent's tool runtime is
# constrained (the rest of the VPC / GKE control-plane traffic keeps working). Tag the
# sandbox workloads with `atlas-locked` to bring them under this policy.
#
# NOTE: The GCE metadata server (169.254.169.254) is link-local and CANNOT be blocked by a
# VPC firewall. The correct control for the metadata-token-theft path is GKE Workload
# Identity with GKE_METADATA (see gke_sandbox.tf), which hides the node SA token from pods.

locals {
  locked_tag = "atlas-locked"
}

# Deny all egress from locked workloads by default (highest-numbered = lowest precedence).
resource "google_compute_firewall" "deny_all_egress" {
  name      = "atlas-deny-all-egress"
  network   = google_compute_network.atlas.id
  direction = "EGRESS"
  priority  = 65533

  deny { protocol = "all" }

  destination_ranges = ["0.0.0.0/0"]
  target_tags        = [local.locked_tag]

  log_config { metadata = "INCLUDE_ALL_METADATA" }
}

# Allow egress only to the restricted Google APIs VIP (Vertex, Model Armor, Artifact Registry…).
resource "google_compute_firewall" "allow_google_apis_egress" {
  name      = "atlas-allow-google-apis-egress"
  network   = google_compute_network.atlas.id
  direction = "EGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  destination_ranges = [var.restricted_apis_vip]
  target_tags        = [local.locked_tag]
}

# Allow egress to the internal subnet (intra-cluster / tool-server calls).
resource "google_compute_firewall" "allow_internal_egress" {
  name      = "atlas-allow-internal-egress"
  network   = google_compute_network.atlas.id
  direction = "EGRESS"
  priority  = 1000

  allow { protocol = "all" }

  destination_ranges = [
    google_compute_subnetwork.atlas.ip_cidr_range,
    "10.20.0.0/16",
    "10.30.0.0/20",
  ]
  target_tags = [local.locked_tag]
}
