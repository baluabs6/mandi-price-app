#!/usr/bin/env bash
# Nightly job (run via Azure DevOps scheduled pipeline / GitHub Actions cron
# / cron container) that dumps the primary Postgres DB and uploads it to
# the AWS S3 DR bucket. Requires: pg_dump, aws CLI configured with
# credentials that have s3:PutObject on the backup bucket.
set -euo pipefail

TIMESTAMP=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
DUMP_FILE="mandi_db_${TIMESTAMP}.sql.gz"
BUCKET="${AWS_BACKUP_BUCKET:?Set AWS_BACKUP_BUCKET}"

echo "Dumping database..."
pg_dump "${DATABASE_URL:?Set DATABASE_URL}" | gzip > "/tmp/${DUMP_FILE}"

echo "Uploading to s3://${BUCKET}/${DUMP_FILE}"
aws s3 cp "/tmp/${DUMP_FILE}" "s3://${BUCKET}/${DUMP_FILE}" --sse AES256

rm -f "/tmp/${DUMP_FILE}"
echo "Backup complete: ${DUMP_FILE}"
