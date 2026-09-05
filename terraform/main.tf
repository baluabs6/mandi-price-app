terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }

  # Recommended: remote state in an Azure Storage Account so Terraform state
  # isn't lost and CI/CD can share it. Fill in after first `terraform apply`
  # with -backend-config, or hardcode once the storage account exists.
  backend "azurerm" {
    # resource_group_name  = "mandiapp-tfstate-rg"
    # storage_account_name = "mandiapptfstate"
    # container_name       = "tfstate"
    # key                  = "mandiapp.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "main" {
  name     = "${local.name_prefix}-rg"
  location = var.location
  tags     = local.tags
}

# ---------------------------------------------------------------------
# Container Registry — stores backend & frontend Docker images
# ---------------------------------------------------------------------
resource "azurerm_container_registry" "acr" {
  name                = var.container_registry_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = local.tags
}

# ---------------------------------------------------------------------
# PostgreSQL Flexible Server
# ---------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "db" {
  name                   = "${local.name_prefix}-psql"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password
  storage_mb             = 32768
  sku_name               = "B_Standard_B1ms" # burstable, cheap — bump for prod load
  zone                   = "1"

  backup_retention_days        = 7
  geo_redundant_backup_enabled = var.environment == "prod" # DR posture for prod

  tags = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "mandi_db" {
  name      = "mandi_db"
  server_id = azurerm_postgresql_flexible_server.db.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.db.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# ---------------------------------------------------------------------
# Redis Cache
# ---------------------------------------------------------------------
resource "azurerm_redis_cache" "cache" {
  name                = "${local.name_prefix}-redis"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  capacity            = 0
  family              = "C"
  sku_name            = "Basic"
  minimum_tls_version = "1.2"
  tags                = local.tags
}

# ---------------------------------------------------------------------
# Container Apps Environment (runs backend + frontend containers)
# ---------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "${local.name_prefix}-logs"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_container_app_environment" "env" {
  name                       = "${local.name_prefix}-cae"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = local.tags
}

resource "azurerm_container_app" "backend" {
  name                         = "${local.name_prefix}-backend"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  revision_mode                = "Single"
  tags                         = local.tags

  registry {
    server               = azurerm_container_registry.acr.login_server
    username              = azurerm_container_registry.acr.admin_username
    password_secret_name  = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }

  secret {
    name  = "database-url"
    value = "postgresql://${var.postgres_admin_username}:${var.postgres_admin_password}@${azurerm_postgresql_flexible_server.db.fqdn}:5432/mandi_db"
  }

  secret {
    name  = "redis-url"
    value = "rediss://:${azurerm_redis_cache.cache.primary_access_key}@${azurerm_redis_cache.cache.hostname}:${azurerm_redis_cache.cache.ssl_port}/0"
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "backend"
      image  = "${azurerm_container_registry.acr.login_server}/mandi-backend:${var.backend_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "FLASK_ENV"
        value = "production"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port       = 5000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

resource "azurerm_container_app" "frontend" {
  name                         = "${local.name_prefix}-frontend"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  revision_mode                = "Single"
  tags                         = local.tags

  registry {
    server               = azurerm_container_registry.acr.login_server
    username              = azurerm_container_registry.acr.admin_username
    password_secret_name  = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "frontend"
      image  = "${azurerm_container_registry.acr.login_server}/mandi-frontend:${var.frontend_image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  ingress {
    external_enabled = true
    target_port       = 80
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}
