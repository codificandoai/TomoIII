# Model Armor template for Demo 1: prompt injection, jailbreak, sensitive data, and RAI filtering.
resource "google_model_armor_template" "demo" {
  location    = var.region
  template_id = "atlas-demo1-template"

  filter_config {
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "LOW_AND_ABOVE"
    }

    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }

    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }

    rai_settings {
      rai_filters {
        filter_type      = "HARASSMENT"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "SEXUALLY_EXPLICIT"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "DANGEROUS"
        confidence_level = "LOW_AND_ABOVE"
      }
    }
  }

  template_metadata {
    enforcement_type = "INSPECT_AND_BLOCK"
  }

  depends_on = [google_project_service.enabled]
}
