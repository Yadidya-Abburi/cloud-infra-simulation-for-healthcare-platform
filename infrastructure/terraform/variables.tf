variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}
variable "db_password" {
  description = "PostgreSQL database password"
  type        = string
  sensitive   = true
}

variable "worker_count" {
  description = "Number of worker containers"
  type        = number
  default     = 1
}

variable "ingress_port" {
  type    = number
  default = 8080
}