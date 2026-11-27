# Provisiona no Aiven o serviço PostgreSQL (plano gratuito), o banco do projeto e o usuário só leitura do dashboard.

terraform {
  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.62"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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

# A API do Aiven devolve a senha gerada por ele como "<redacted>", então a senha é definida aqui.
resource "random_password" "dashboard" {
  length  = 32
  special = false
}

resource "aiven_pg_user" "dashboard" {
  project      = aiven_pg.postgresql.project
  service_name = aiven_pg.postgresql.service_name
  username     = var.dashboard_username
  password     = random_password.dashboard.result
}
