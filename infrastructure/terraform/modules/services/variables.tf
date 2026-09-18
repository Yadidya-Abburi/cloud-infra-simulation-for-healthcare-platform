variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "frontend_network_id" {
  description = "Frontend Docker network ID"
  type        = string
}

variable "backend_network_id" {
  description = "Backend Docker network ID"
  type        = string
}

variable "postgres_volume_name" {
  description = "PostgreSQL persistent volume name"
  type        = string
}

variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "worker_count" {
  description = "Number of background workers"
  type        = number
  default     = 1
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "healthcare"
}

variable "db_user" {
  description = "PostgreSQL database user"
  type        = string
  default     = "postgres"
}

variable "ai_image" {
  type    = string
  default = "cloud-infra-simulation-for-healthcare-platform-ai-service:latest"
}

variable "mock_ehr_image" {
  type    = string
  default = "cloud-infra-simulation-for-healthcare-platform-mock-ehr:latest"
}

variable "worker_image" {
  type    = string
  default = "cloud-infra-simulation-for-healthcare-platform-worker:latest"
}

variable "api_image" {
  description = "API Blue Docker image"
  type        = string
  default     = "cloud-infra-simulation-for-healthcare-platform-api-blue:latest"
}

variable "nginx_image" {
  description = "NGINX ingress Docker image"
  type        = string
  default     = "nginx:1.25-alpine"
}

variable "ingress_port" {
  description = "Host port for NGINX ingress"
  type        = number
  default     = 8080
}