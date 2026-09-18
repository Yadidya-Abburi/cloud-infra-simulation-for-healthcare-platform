# Prometheus Container
resource "docker_container" "prometheus" {
  name  = "${var.environment}-prometheus"
  image = "prom/prometheus:v2.50.1"

  restart = "always"

  command = [
    "--config.file=/etc/prometheus/prometheus.yml",
    "--storage.tsdb.path=/prometheus",
    "--web.console.libraries=/usr/share/prometheus/console_libraries",
    "--web.console.templates=/usr/share/prometheus/consoles"
  ]

  ports {
    internal = 9090
    external = var.prometheus_port
  }

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["prometheus"]
  }

  volumes {
    host_path      = abspath("${path.root}/../../monitoring/prometheus/prometheus.yml")
    container_path = "/etc/prometheus/prometheus.yml"
    read_only      = true
  }

  volumes {
    host_path      = abspath("${path.root}/../../monitoring/prometheus/alerts.yml")
    container_path = "/etc/prometheus/alerts.yml"
    read_only      = true
  }
}

# Grafana Container
resource "docker_container" "grafana" {
  name  = "${var.environment}-grafana"
  image = "grafana/grafana:10.3.3"

  restart = "always"

  env = [
    "GF_SECURITY_ADMIN_PASSWORD=${var.grafana_admin_password}",
    "GF_USERS_ALLOW_SIGN_UP=false",
    "GF_ANALYTICS_REPORTING_ENABLED=false",
    "GF_AUTH_ANONYMOUS_ENABLED=true",
    "GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer"
  ]

  ports {
    internal = 3000
    external = var.grafana_port
  }

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["grafana"]
  }

  volumes {
    host_path      = abspath("${path.root}/../../monitoring/grafana/provisioning/datasources")
    container_path = "/etc/grafana/provisioning/datasources"
    read_only      = true
  }

  volumes {
    host_path      = abspath("${path.root}/../../monitoring/grafana/provisioning/dashboards")
    container_path = "/etc/grafana/provisioning/dashboards"
    read_only      = true
  }

  depends_on = [
    docker_container.prometheus
  ]
}
