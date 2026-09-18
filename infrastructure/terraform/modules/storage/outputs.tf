output "postgres_volume_name" {
  description = "PostgreSQL Docker volume name"
  value       = docker_volume.postgres_data.name
}

output "postgres_volume_id" {
  description = "PostgreSQL Docker volume ID"
  value       = docker_volume.postgres_data.id
}