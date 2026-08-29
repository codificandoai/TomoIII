# Demo 2 — the network the agent's tool runtime egresses through.
# Private Google Access + Cloud NAT give controlled egress; the firewall rules
# (firewall.tf) then lock it down so a token-stealing payload has nowhere to go.

resource "google_compute_network" "atlas" {
  name                    = "atlas-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.guardrails]
}

resource "google_compute_subnetwork" "atlas" {
  name          = "atlas-subnet"
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
  network       = google_compute_network.atlas.id

  # Reach Google APIs over the restricted VIP without a public IP (VPC-SC friendly).
  private_ip_google_access = true

  # Secondary ranges for GKE pods/services (Demo 2 sandbox cluster).
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.20.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.30.0.0/20"
  }
}

# Route restricted.googleapis.com through the restricted VIP.
resource "google_compute_route" "restricted_apis" {
  name             = "atlas-restricted-apis"
  network          = google_compute_network.atlas.id
  dest_range       = var.restricted_apis_vip
  next_hop_gateway = "default-internet-gateway"
  priority         = 1000
}

# Cloud NAT so allowed egress has a path, without giving instances public IPs.
resource "google_compute_router" "atlas" {
  name    = "atlas-router"
  region  = var.region
  network = google_compute_network.atlas.id
}

resource "google_compute_router_nat" "atlas" {
  name                               = "atlas-nat"
  router                             = google_compute_router.atlas.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.atlas.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
