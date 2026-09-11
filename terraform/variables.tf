variable "project_name" {
  description = "Short name used to prefix Azure resources"
  type        = string
  default     = "mandiapp"
}

variable "environment" {
  description = "deployment environment: dev / staging / prod"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "Central India"
}

variable "postgres_admin_username" {
  type    = string
  default = "<YOUR_DB_ADMIN_USER>"
}

variable "postgres_admin_password" {
  description = "Set via TF_VAR_postgres_admin_password or a secret store — do not commit."
  type        = string
  sensitive   = true
}

variable "container_registry_name" {
  description = "Globally-unique ACR name (letters/numbers only)"
  type        = string
}

variable "backend_image_tag" {
  type    = string
  default = "latest"
}

variable "frontend_image_tag" {
  type    = string
  default = "latest"
}
