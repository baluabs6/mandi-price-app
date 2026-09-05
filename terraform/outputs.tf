output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.db.fqdn
}

output "redis_hostname" {
  value = azurerm_redis_cache.cache.hostname
}

output "backend_url" {
  value = azurerm_container_app.backend.latest_revision_fqdn
}

output "frontend_url" {
  value = azurerm_container_app.frontend.latest_revision_fqdn
}
