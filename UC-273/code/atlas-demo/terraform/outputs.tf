output "service_url" {
  description = "Public URL of the Atlas demo console."
  value       = google_cloud_run_v2_service.atlas.uri
}

output "image" {
  description = "Fully-qualified image the service deploys."
  value       = local.image
}

output "artifact_registry_repo" {
  description = "Artifact Registry repo path for docker push."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_id}"
}

output "runtime_service_account" {
  description = "Service account the Cloud Run service runs as."
  value       = google_service_account.atlas.email
}

output "model_armor_template" {
  description = "Model Armor template resource name."
  value       = google_model_armor_template.demo.name
}

output "shieldgemma_endpoint" {
  description = "Vertex AI endpoint resource ID for ShieldGemma moderation."
  value       = google_vertex_ai_endpoint.shieldgemma.id
}

