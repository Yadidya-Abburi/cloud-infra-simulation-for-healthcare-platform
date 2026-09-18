resource "docker_volume" "postgres_data" {
  name = "${var.environment}-postgres-data"
}