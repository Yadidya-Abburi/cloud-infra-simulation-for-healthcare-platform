output "postgres_container_name" {
  description = "PostgreSQL container name"
  value       = docker_container.postgres.name
}

output "redis_container_name" {
  description = "Redis container name"
  value       = docker_container.redis.name
}

output "ai_service_container_name" {
  value = docker_container.ai_service.name
}

output "mock_ehr_container_name" {
  value = docker_container.mock_ehr.name
}

output "worker_container_names" {
  value = docker_container.worker[*].name
}
output "api_container_name" {
  value = docker_container.api_blue.name
}

output "nginx_container_name" {
  value = docker_container.nginx.name
}