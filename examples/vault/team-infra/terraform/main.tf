terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {}
variable "region" { default = "us-central1" }

resource "google_container_cluster" "primary" {
  name     = "platform-cluster"
  location = var.region
  initial_node_count = 3
}
