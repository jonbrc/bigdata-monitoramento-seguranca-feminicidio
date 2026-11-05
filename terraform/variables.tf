# Variáveis de entrada do Terraform: token da API e projeto do Aiven, e nome do banco.

variable "aiven_api_token" {
  description = "Token para autenticação da API do Aiven"
  type        = string
  sensitive   = true
}

variable "aiven_project_name" {
  description = "Nome do projeto criado no Aiven"
  type        = string
}

variable "pg_database_name" {
  description = "Nome do banco de dados do projeto"
  type        = string
  default     = "seguranca_publica"
}
