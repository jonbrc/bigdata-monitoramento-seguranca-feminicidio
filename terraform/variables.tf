variable "aiven_api_token" {
    description = "token para autenticação da API do Aiven"
    type = string
    sensitive = true
}

variable "aiven_project_name" {
  description = "nome do projeto criado no aiven"
  type = string
}