output "prometheus_url" {
  description = "Prometheus UI URL"
  value       = "http://localhost:${var.prometheus_port}"
}

output "grafana_url" {
  description = "Grafana Dashboards URL"
  value       = "http://localhost:${var.grafana_port}"
}
