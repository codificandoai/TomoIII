# Dedicated runtime service account for the Cloud Run service (least privilege).
resource "google_service_account" "atlas" {
  account_id   = "${var.service_name}-sa"
  display_name = "Atlas agent runtime"
}

# Call Gemini / Vertex on the Gemini Enterprise Agent Platform.
resource "google_project_iam_member" "aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.atlas.email}"
}

# Invoke Model Armor sanitize endpoints (Demo 1 live path).
resource "google_project_iam_member" "modelarmor_user" {
  project = var.project_id
  role    = "roles/modelarmor.user"
  member  = "serviceAccount:${google_service_account.atlas.email}"
}
