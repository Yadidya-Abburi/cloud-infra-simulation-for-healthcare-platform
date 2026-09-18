variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "backend_network_id" {
  description = "Backend Docker network ID for scraping internal metrics"
  type        = string
}

variable "prometheus_port" {
  description = "Host port for Prometheus UI"
  type        = number
  default     = 9090
}

variable "grafana_port" {
  description = "Host port for Grafana Dashboards"
  type        = number
  default     = 3000
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  default     = "admin"
}
