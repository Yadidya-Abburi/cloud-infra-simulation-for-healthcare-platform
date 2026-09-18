output "frontend_network_id" {
  description = "Frontend Docker network ID"
  value       = docker_network.frontend.id
}

output "backend_network_id" {
  description = "Backend Docker network ID"
  value       = docker_network.backend.id
}

output "frontend_network_name" {
  description = "Frontend Docker network name"
  value       = docker_network.frontend.name
}

output "backend_network_name" {
  description = "Backend Docker network name"
  value       = docker_network.backend.name
}