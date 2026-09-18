module "network" {
  source = "./modules/network"

  environment = var.environment
}

module "storage" {
  source = "./modules/storage"

  environment = var.environment
}
module "services" {
  source = "./modules/services"

  environment = var.environment

  frontend_network_id = module.network.frontend_network_id
  backend_network_id  = module.network.backend_network_id

  postgres_volume_name = module.storage.postgres_volume_name

  db_password  = var.db_password
  worker_count = var.worker_count
  ingress_port = var.ingress_port
}

module "monitoring" {
  source = "./modules/monitoring"

  environment        = var.environment
  backend_network_id = module.network.backend_network_id
}