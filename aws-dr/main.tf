/*
Disaster Recovery on AWS
------------------------
Primary infra lives on Azure. For DR we keep a cold/warm standby path on AWS:
  1. Nightly `pg_dump` of the Azure Postgres DB, encrypted and pushed to
     this S3 bucket (versioned + lifecycle-managed).
  2. In a declared disaster, `restore.sh` spins up an RDS Postgres instance
     from the latest dump and an ECS Fargate service running the same
     backend Docker image (pulled from a mirrored ECR repo) — see
     `restore.sh` for the manual/scripted steps.
This is a cost-conscious "backup + redeploy" DR pattern (RPO ~24h) rather
than always-on multi-cloud replication, appropriate for a public-good
transparency site rather than a transactional system.
*/

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "ap-south-1" # Mumbai — closest to Azure Central India for restore speed
}

variable "project_name" {
  type    = string
  default = "mandiapp"
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-db-backups"
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    expiration {
      days = 90
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ECR repo to mirror the backend image, so a restore doesn't depend on
# Azure Container Registry being reachable.
resource "aws_ecr_repository" "backend_mirror" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"
}

output "backup_bucket" {
  value = aws_s3_bucket.backups.bucket
}

output "ecr_repo_url" {
  value = aws_ecr_repository.backend_mirror.repository_url
}
