# Docker repository that holds the Atlas image.
resource "google_artifact_registry_repository" "atlas" {
  location      = var.region
  repository_id = var.repo_id
  description   = "Atlas agent-security demo images"
  format        = "DOCKER"

  depends_on = [google_project_service.enabled]
}

locals {
  image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_id}/${var.service_name}:${var.image_tag}"
}
