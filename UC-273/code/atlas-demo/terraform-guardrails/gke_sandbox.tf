# Demo 2 — the sandboxed runtime for the agent's code-interpreter tool.
# A gVisor node pool intercepts syscalls; Workload Identity (GKE_METADATA) removes the
# node service-account token from pods, closing the metadata-theft path.
#
# Pods opt into gVisor with:  runtimeClassName: gvisor
#                             nodeSelector: { sandbox.gke.io/runtime: gvisor }

resource "google_service_account" "gke_node" {
  count        = var.enable_gke_sandbox ? 1 : 0
  account_id   = "atlas-gke-node"
  display_name = "Atlas GKE sandbox node SA"
}

resource "google_container_cluster" "atlas" {
  count    = var.enable_gke_sandbox ? 1 : 0
  name     = "atlas-sandbox"
  location = var.zone

  network    = google_compute_network.atlas.id
  subnetwork = google_compute_subnetwork.atlas.id

  # Manage node pools explicitly (gVisor must live on a non-default pool).
  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel {
    channel = "REGULAR"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  depends_on = [google_project_service.guardrails]
}

resource "google_container_node_pool" "sandboxed" {
  count    = var.enable_gke_sandbox ? 1 : 0
  name     = "sandboxed"
  cluster  = google_container_cluster.atlas[0].id
  location = var.zone

  node_count = 1

  node_config {
    machine_type = "e2-standard-2"
    image_type   = "COS_CONTAINERD" # required for gVisor
    tags         = [local.locked_tag]

    service_account = google_service_account.gke_node[0].email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    # gVisor sandbox.
    sandbox_config {
      sandbox_type = "gvisor"
    }

    # Hide the node metadata/token from workloads.
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
