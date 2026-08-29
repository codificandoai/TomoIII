# Demo 4 — the remediation target: the hardcoded API key the "bad PR" embedded should
# live here instead. Grant the Atlas Cloud Run SA access so the app reads it at runtime.

resource "google_secret_manager_secret" "atlas_api_key" {
  secret_id = "atlas-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.guardrails]
}

# Optional placeholder version so the secret is usable immediately in the demo.
resource "google_secret_manager_secret_version" "atlas_api_key" {
  secret      = google_secret_manager_secret.atlas_api_key.id
  secret_data = "replace-me-with-a-real-rotated-key"
}

resource "google_secret_manager_secret_iam_member" "app_accessor" {
  count     = var.app_service_account_email == "" ? 0 : 1
  secret_id = google_secret_manager_secret.atlas_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.app_service_account_email}"
}
