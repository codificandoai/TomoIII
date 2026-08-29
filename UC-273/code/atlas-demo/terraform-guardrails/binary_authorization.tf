# Demo 4 — Binary Authorization: only signed/attested images may be admitted.
# An unsigned image (the "bad PR" deploy) is refused at admission.

resource "google_container_analysis_note" "attestor" {
  count = var.enable_binary_authorization ? 1 : 0
  name  = "atlas-attestor-note"

  attestation_authority {
    hint {
      human_readable_name = "Atlas build attestor"
    }
  }

  depends_on = [google_project_service.guardrails]
}

resource "google_binary_authorization_attestor" "atlas" {
  count = var.enable_binary_authorization ? 1 : 0
  name  = "atlas-attestor"

  attestation_authority_note {
    note_reference = google_container_analysis_note.attestor[0].name

    # Attach a PKIX key when provided; otherwise create the attestor and add keys later.
    dynamic "public_keys" {
      for_each = var.attestor_public_key_pkix == "" ? [] : [1]
      content {
        id = var.attestor_public_key_id
        pkix_public_key {
          public_key_pem      = var.attestor_public_key_pkix
          signature_algorithm = "ECDSA_P256_SHA256"
        }
      }
    }
  }
}

resource "google_binary_authorization_policy" "atlas" {
  count = var.enable_binary_authorization ? 1 : 0

  # Google-managed system images are always allowed.
  admission_whitelist_patterns {
    name_pattern = "gcr.io/google_containers/*"
  }
  admission_whitelist_patterns {
    name_pattern = "gke.gcr.io/*"
  }

  default_admission_rule {
    evaluation_mode  = "REQUIRE_ATTESTATION"
    enforcement_mode = "ENFORCED_BLOCK_AND_AUDIT_LOG"
    require_attestation_by = [
      google_binary_authorization_attestor.atlas[0].name,
    ]
  }

  global_policy_evaluation_mode = "ENABLE"
}
