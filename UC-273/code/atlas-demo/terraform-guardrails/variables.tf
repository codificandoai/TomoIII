variable "project_id" {
  type        = string
  description = "GCP project ID for the demo."
}

variable "project_number" {
  type        = string
  description = "GCP project NUMBER (required for the VPC-SC perimeter). `gcloud projects describe <id> --format='value(projectNumber)'`."
  default     = ""
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

# --- Feature toggles: enable a demo's infra control independently -----------------------
variable "enable_gke_sandbox" {
  type        = bool
  description = "Demo 2: GKE cluster with a gVisor-sandboxed node pool + Workload Identity."
  default     = false
}

variable "enable_vpc_sc" {
  type        = bool
  description = "Demo 2: VPC Service Controls perimeter. Requires an organization + Access Context Manager policy."
  default     = false
}

variable "enable_binary_authorization" {
  type        = bool
  description = "Demo 4: Binary Authorization attestor + require-attestation policy."
  default     = false
}

variable "enable_policy_controller" {
  type        = bool
  description = "Demo 4: Policy Controller (OPA Gatekeeper) via GKE Hub. Requires enable_gke_sandbox."
  default     = false
}

# --- VPC-SC inputs ----------------------------------------------------------------------
variable "access_policy_id" {
  type        = string
  description = "Access Context Manager policy ID (numeric). Org-level. `gcloud access-context-manager policies list`."
  default     = ""
}

# --- Binary Authorization inputs --------------------------------------------------------
variable "attestor_public_key_pkix" {
  type        = string
  description = "Optional PKIX (PEM) public key for the attestor. Empty = attestor created without keys (add later)."
  default     = ""
}

variable "attestor_public_key_id" {
  type        = string
  description = "Key id for the PKIX public key above."
  default     = ""
}

# --- Cross-module wiring ----------------------------------------------------------------
variable "app_service_account_email" {
  type        = string
  description = "Runtime SA of the Atlas Cloud Run service (from the app module output). Granted Secret Manager access if set."
  default     = ""
}

# --- Egress allowlist -------------------------------------------------------------------
variable "restricted_apis_vip" {
  type        = string
  description = "restricted.googleapis.com VIP range that private Google access + VPC-SC route through."
  default     = "199.36.153.4/30"
}
