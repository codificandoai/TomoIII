# Vertex AI endpoint for ShieldGemma moderation in Demo 1.
resource "google_vertex_ai_endpoint" "shieldgemma" {
  name         = "8829104812"
  display_name = "atlas-shieldgemma-endpoint"
  location     = var.region
  description  = "Vertex AI Endpoint for ShieldGemma safety classification"
  depends_on   = [google_project_service.enabled]
}
