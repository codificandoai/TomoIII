# Enable the Google Cloud APIs the demo depends on.
locals {
  services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",     # Gemini Enterprise Agent Platform / Vertex
    "modelarmor.googleapis.com",     # Demo 1 (optional live path)
    "dlp.googleapis.com",            # Demo 1 (optional live DLP)
    "securitycenter.googleapis.com", # Demo 4
    "binaryauthorization.googleapis.com", # Demo 4
  ]
}

resource "google_project_service" "enabled" {
  for_each                   = toset(local.services)
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}
