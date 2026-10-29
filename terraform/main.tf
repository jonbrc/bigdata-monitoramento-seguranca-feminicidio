terraform {
  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.62"
    }
  }
}

provider "aiven" {
  api_token = var.aiven_api_token
}

resource "aiven_pg" "postgresql" {
  project      = var.aiven_project_name
  service_name = "db-seguranca-publica"
  cloud_name   = "do-nyc"
  plan         = "free-1-1gb"

  termination_protection = false
}

resource "aiven_pg_database" "projeto" {
  project       = aiven_pg.postgresql.project
  service_name  = aiven_pg.postgresql.service_name
  database_name = var.pg_database_name
}