output "postgres_container_name" {
  value = module.services.postgres_container_name
}

output "redis_container_name" {
  value = module.services.redis_container_name
}

output "ingress_url" {
  value = "http://localhost:${var.ingress_port}"
}

output "prometheus_url" {
  value = module.monitoring.prometheus_url
}

output "grafana_url" {
  value = module.monitoring.grafana_url
}