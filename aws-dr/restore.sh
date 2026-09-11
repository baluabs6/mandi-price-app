#!/usr/bin/env bash
# Disaster-recovery restore runbook. Intended to be run manually (or wired
# into an incident-response pipeline) when Azure is unreachable.
#
# Steps this performs:
#   1. Provision (or reuse) an RDS Postgres instance in AWS.
#   2. Download the latest backup from S3.
#   3. Restore it into RDS.
#   4. Print the connection string to point a redeployed backend at.
#
# This is deliberately a script, not always-on infra, to keep DR cost low
# for a public-good site — accept an RPO of ~24h / RTO of ~1-2h.
set -euo pipefail

BUCKET="${AWS_BACKUP_BUCKET:?Set AWS_BACKUP_BUCKET}"
RDS_ENDPOINT="${RDS_ENDPOINT:?Set RDS_ENDPOINT (create the RDS instance first, e.g. via aws rds create-db-instance)}"
RDS_USER="${RDS_USER:-<YOUR_DB_ADMIN_USER>}"
RDS_DB="${RDS_DB:-<YOUR_DB_NAME>}"

echo "Finding latest backup in s3://${BUCKET} ..."
LATEST=$(aws s3 ls "s3://${BUCKET}/" | sort | tail -n 1 | awk '{print $4}')
if [ -z "${LATEST}" ]; then
  echo "No backups found in bucket." >&2
  exit 1
fi
echo "Latest backup: ${LATEST}"

aws s3 cp "s3://${BUCKET}/${LATEST}" "/tmp/${LATEST}"
gunzip -f "/tmp/${LATEST}"
SQL_FILE="/tmp/${LATEST%.gz}"

echo "Restoring into RDS at ${RDS_ENDPOINT} ..."
PGPASSWORD="${RDS_PASSWORD:?Set RDS_PASSWORD}" psql \
  -h "${RDS_ENDPOINT}" -U "${RDS_USER}" -d "${RDS_DB}" -f "${SQL_FILE}"

echo "Restore complete."
echo "Point the backend DATABASE_URL at:"
echo "postgresql://${RDS_USER}:<password>@${RDS_ENDPOINT}:5432/${RDS_DB}"
echo "Then redeploy the backend container (pulled from ECR mirror) to ECS Fargate / App Runner."
