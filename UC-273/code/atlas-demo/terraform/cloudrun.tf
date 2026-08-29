# The Atlas Cloud Run service.
resource "google_cloud_run_v2_service" "atlas" {
  name     = var.service_name
  location = var.region

  # Keep ingress open for the demo; tighten to INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER
  # when fronting with Agent Gateway / a load balancer.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.atlas.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    # Demo 2: route egress through the guardrails VPC so the firewall / Cloud NAT /
    # VPC-SC apply to the running agent. Set vpc_network + vpc_subnet (from the
    # terraform-guardrails outputs) to enable; leave empty for plain internet egress.
    dynamic "vpc_access" {
      for_each = var.vpc_subnet == "" ? [] : [1]
      content {
        egress = "ALL_TRAFFIC"
        network_interfaces {
          network    = var.vpc_network
          subnetwork = var.vpc_subnet
        }
      }
    }

    containers {
      image = local.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "MODEL_NAME"
        value = var.model_name
      }
      env {
        name  = "ENABLE_LLM"
        value = tostring(var.enable_llm)
      }
      env {
        name  = "MODEL_ARMOR_TEMPLATE"
        value = var.model_armor_template != "" ? var.model_armor_template : google_model_armor_template.demo.name
      }
      env {
        name  = "SHIELDGEMMA_ENDPOINT"
        value = var.shieldgemma_endpoint != "" ? var.shieldgemma_endpoint : google_vertex_ai_endpoint.shieldgemma.id
      }
      env {
        name  = "ALLOWED_EGRESS_HOSTS"
        value = var.allowed_egress_hosts
      }
      env {
        name  = "FINANCE_TRUSTED_IDENTITY"
        value = var.finance_trusted_identity
      }

      # Default guardrail flags (all OFF by default for a clean baseline attack).
      dynamic "env" {
        for_each = var.default_guardrails
        content {
          name  = env.key
          value = tostring(env.value)
        }
      }
    }
  }

  depends_on = [
    google_project_service.enabled,
    google_artifact_registry_repository.atlas,
  ]
}

# Public access for the demo (toggle via allow_unauthenticated).
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.atlas.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
