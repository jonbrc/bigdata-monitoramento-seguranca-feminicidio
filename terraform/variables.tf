variable "aiven_api_token" {
    description = "token para autenticação da API do Aiven"
    type = string
    sensitive = true
}

variable "aiven_project_name" {
  description = "nome do projeto criado no aiven"
  type = string
}

variable "pg_database_name" {
  description = "Nome do banco de dados do projeto"
  type        = string
  default     = "seguranca_publica"
}