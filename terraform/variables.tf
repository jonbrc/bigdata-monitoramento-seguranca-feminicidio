# Variáveis de entrada do Terraform: token da API e projeto do Aiven, nome do banco e usuário do dashboard.

variable "aiven_api_token" {
  description = "Token para autenticação da API do Aiven"
  type        = string
  sensitive   = true
}

variable "aiven_project_name" {
  description = "Nome do projeto criado no Aiven"
  type        = string
}

variable "dashboard_username" {
  description = "Usuário do banco usado pelo dashboard (as permissões de leitura são concedidas pelo sql/schema.sql)"
  type        = string
  default     = "dashboard_leitura"
}

variable "pg_database_name" {
  description = "Nome do banco de dados do projeto"
  type        = string
  default     = "seguranca_publica"
}
