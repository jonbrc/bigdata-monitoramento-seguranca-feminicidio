terraform {
  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = ">= 4.0.0" # check out the latest version in the release section
    }
  }
}

provider "aiven" {
  api_token = var.aiven_api_token
}

resource "aiven_pg" "postgresql" {
  project                = var.aiven_project_name
  service_name           = "db-seguranca-publica"
  cloud_name             = "do-nyc"
  plan                   = "free-1-1gb"

  termination_protection = false
}

