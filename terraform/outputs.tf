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