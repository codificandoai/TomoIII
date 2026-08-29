output "network" {
  description = "VPC self-link to attach the Cloud Run service to (Demo 2 egress)."
  value       = google_compute_network.atlas.id
}

output "subnet" {
  description = "Subnet self-link for Cloud Run direct VPC egress."
  value       = google_compute_subnetwork.atlas.id
}

output "locked_tag" {
  description = "Network tag that brings a workload under the egress lockdown."
  value       = local.locked_tag
}

output "gke_cluster" {
  description = "Sandboxed GKE cluster name (if enabled)."
  value       = var.enable_gke_sandbox ? google_container_cluster.atlas[0].name : "(disabled)"
}

output "attestor" {
  description = "Binary Authorization attestor name (if enabled)."
  value       = var.enable_binary_authorization ? google_binary_authorization_attestor.atlas[0].name : "(disabled)"
}

output "api_key_secret" {
  description = "Secret Manager secret id for the remediated API key."
  value       = google_secret_manager_secret.atlas_api_key.secret_id
}
