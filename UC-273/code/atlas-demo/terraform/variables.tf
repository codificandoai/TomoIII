variable "project_id" {
  type        = string
  description = "GCP project ID for the demo."
}

variable "region" {
  type        = string
  description = "Region for Cloud Run and Artifact Registry."
  default     = "us-central1"
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name."
  default     = "atlas-agent"
}

variable "repo_id" {
  type        = string
  description = "Artifact Registry repository ID."
  default     = "atlas"
}

variable "image_tag" {
  type        = string
  description = "Container image tag to deploy."
  default     = "latest"
}

variable "model_name" {
  type        = string
  description = "Gemini model served on the Gemini Enterprise Agent Platform."
  default     = "gemini-3.5-flash"
}

variable "enable_llm" {
  type        = bool
  description = "Use the live Gemini planner (true) or the deterministic planner (false)."
  default     = false
}

variable "model_armor_template" {
  type        = string
  description = "Optional Model Armor template resource name. Empty = heuristic fallback."
  default     = ""
}

variable "shieldgemma_endpoint" {
  type        = string
  description = "Optional ShieldGemma endpoint resource name or URL. Empty = use created Vertex AI endpoint."
  default     = ""
}

variable "allowed_egress_hosts" {
  type        = string
  description = "Comma-separated egress allowlist for the app-level egress policy (Demo 2)."
  default     = "finance.internal,api.atlas.demo"
}

variable "finance_trusted_identity" {
  type        = string
  description = "Identity the finance tool-server trusts for the planner agent (Demo 3)."
  default     = "spiffe://atlas/planner"
}

variable "default_guardrails" {
  type        = map(bool)
  description = "Default guardrail flags baked into the revision. Keep OFF for a clean baseline."
  default = {
    ENABLE_MODEL_ARMOR   = false
    ENABLE_DLP_REDACTION = false
    ENABLE_SHIELDGEMMA   = false
    ENABLE_BOLA_GUARD    = false
    ENABLE_EGRESS_POLICY = false
    ENABLE_AGENT_IDENTITY = false
  }
}

variable "allow_unauthenticated" {
  type        = bool
  description = "Allow public (unauthenticated) access to the Cloud Run service."
  default     = true
}

variable "vpc_network" {
  type        = string
  description = "Optional: VPC self-link for Cloud Run direct VPC egress (from terraform-guardrails `network` output). Empty = plain internet egress."
  default     = ""
}

variable "vpc_subnet" {
  type        = string
  description = "Optional: subnet self-link for Cloud Run direct VPC egress (from terraform-guardrails `subnet` output)."
  default     = ""
}
