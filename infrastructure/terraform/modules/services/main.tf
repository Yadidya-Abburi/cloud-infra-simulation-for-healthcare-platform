resource "docker_container" "postgres" {
  name  = "${var.environment}-postgres"
  image = "postgres:16-alpine"

  restart = "always"

  env = [
    "POSTGRES_DB=${var.db_name}",
    "POSTGRES_USER=${var.db_user}",
    "POSTGRES_PASSWORD=${var.db_password}"
  ]

  networks_advanced {
    name = var.backend_network_id

    aliases = ["postgres"]
  }

  volumes {
    volume_name    = var.postgres_volume_name
    container_path = "/var/lib/postgresql/data"
  }

  volumes {
    host_path      = abspath("${path.root}/../../infrastructure/database/init.sql")
    container_path = "/docker-entrypoint-initdb.d/init.sql"
    read_only      = true
  }

  healthcheck {
    test = [
      "CMD-SHELL",
      "pg_isready -U ${var.db_user} -d ${var.db_name}"
    ]

    interval = "10s"
    timeout  = "5s"
    retries  = 5
  }
}

resource "docker_container" "redis" {
  name  = "${var.environment}-redis"
  image = "redis:7.2-alpine"

  restart = "always"

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["redis"]
  }

  healthcheck {
    test = [
      "CMD",
      "redis-cli",
      "ping"
    ]

    interval = "10s"
    timeout  = "3s"
    retries  = 5
  }
}

resource "docker_container" "ai_service" {
  name  = "${var.environment}-ai-service"
  image = var.ai_image

  restart = "always"

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["ai-service"]
  }

  healthcheck {
    test = [
      "CMD",
      "python",
      "-c",
      "import urllib.request; urllib.request.urlopen('http://localhost:8082/health')"
    ]

    interval = "15s"
    timeout  = "5s"
    retries  = 3
  }
}

resource "docker_container" "mock_ehr" {
  name  = "${var.environment}-mock-ehr"
  image = var.mock_ehr_image

  restart = "always"

  env = [
    "EHR_MODE=normal"
  ]

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["mock-ehr"]
  }

  healthcheck {
    test = [
      "CMD",
      "python",
      "-c",
      "import urllib.request; urllib.request.urlopen('http://localhost:8083/health')"
    ]

    interval = "15s"
    timeout  = "5s"
    retries  = 3
  }
}

resource "docker_container" "worker" {
  count = var.worker_count

  name  = "${var.environment}-worker-${count.index + 1}"
  image = var.worker_image

  restart = "always"

  env = [
    "DB_HOST=postgres",
    "DB_NAME=${var.db_name}",
    "DB_PASSWORD=${var.db_password}",
    "DB_PORT=5432",
    "DB_USER=${var.db_user}",
    "EHR_SERVICE_URL=http://mock-ehr:8083",
    "METRICS_PORT=9100",
    "REDIS_HOST=redis",
    "REDIS_PORT=6379"
  ]

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["worker-${count.index + 1}"]
  }

  depends_on = [
    docker_container.postgres,
    docker_container.redis,
    docker_container.mock_ehr
  ]
}

resource "docker_container" "api_blue" {
  name  = "${var.environment}-api-blue"
  image = var.api_image

  restart = "always"

  env = [
    "AI_SERVICE_URL=http://ai-service:8082",
    "APP_VERSION=v1.0.0",
    "DB_HOST=postgres",
    "DB_NAME=${var.db_name}",
    "DB_PASSWORD=${var.db_password}",
    "DB_PORT=5432",
    "DB_USER=${var.db_user}",
    "DEPLOYMENT_COLOR=blue",
    "REDIS_HOST=redis",
    "REDIS_PORT=6379"
  ]

  networks_advanced {
    name    = var.frontend_network_id
    aliases = ["api-blue"]
  }

  networks_advanced {
    name    = var.backend_network_id
    aliases = ["api-blue"]
  }

  healthcheck {
    test = [
      "CMD",
      "curl",
      "-f",
      "http://localhost:8000/ready"
    ]

    interval = "10s"
    timeout  = "5s"
    retries  = 3
  }

  depends_on = [
    docker_container.postgres,
    docker_container.redis,
    docker_container.ai_service
  ]
}

resource "docker_container" "nginx" {
  name  = "${var.environment}-nginx"
  image = var.nginx_image

  restart = "always"

  ports {
    internal = 80
    external = var.ingress_port
  }

  networks_advanced {
    name = var.frontend_network_id
  }

  volumes {
    host_path      = abspath("${path.root}/../../deployment/nginx/nginx.conf")
    container_path = "/etc/nginx/nginx.conf"
    read_only      = true
  }

  volumes {
    host_path      = abspath("${path.root}/../../deployment/nginx/conf.d")
    container_path = "/etc/nginx/conf.d"
    read_only      = true
  }

  depends_on = [
    docker_container.api_blue
  ]

  healthcheck {
    test = [
      "CMD",
      "wget",
      "-qO-",
      "http://127.0.0.1/nginx-health"
    ]

    interval = "10s"
    timeout  = "3s"
    retries  = 3
  }
}