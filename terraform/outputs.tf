# Saídas do Terraform: host, porta, nome do banco, URIs de conexão e credenciais do usuário do dashboard (sensíveis).

output "pg_host" {
  description = "Host do serviço PostgreSQL"
  value       = aiven_pg.postgresql.service_host
}

output "pg_port" {
  description = "Porta do serviço PostgreSQL"
  value       = aiven_pg.postgresql.service_port
}

output "pg_database" {
  description = "Nome do banco do projeto"
  value       = aiven_pg_database.projeto.database_name
}

output "pg_uri" {
  description = "URI de conexão (aponta para o defaultdb)"
  value       = aiven_pg.postgresql.service_uri
  sensitive   = true
}

output "pg_database_uri" {
  description = "URI de conexão apontando para o banco do projeto"
  value       = replace(aiven_pg.postgresql.service_uri, "/defaultdb", "/${aiven_pg_database.projeto.database_name}")
  sensitive   = true
}

output "dashboard_usuario" {
  description = "Usuário só leitura do dashboard"
  value       = aiven_pg_user.dashboard.username
}

output "dashboard_senha" {
  description = "Senha do usuário do dashboard (use em DB_PASSWORD nos Secrets do Streamlit)"
  value       = aiven_pg_user.dashboard.password
  sensitive   = true
}
