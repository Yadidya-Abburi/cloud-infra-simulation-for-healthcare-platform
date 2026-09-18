resource "docker_network" "frontend" {
  name = "${var.environment}-frontend-net"
}

resource "docker_network" "backend" {
  name = "${var.environment}-backend-net"
}
