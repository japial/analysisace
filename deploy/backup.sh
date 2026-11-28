#!/bin/sh
# Daily backups for docker-compose.prod.yml: a PostgreSQL dump and a copy of the encrypted
# documents, written to /backups and kept for BACKUP_KEEP_DAYS days. Restoring is described
# in docs/DEPLOY.md. Documents are useless without DATA_ENCRYPTION_KEY, so keep that key
# safe as well, but never in the same place as these files.
set -u

keep="${BACKUP_KEEP_DAYS:-14}"
interval="${BACKUP_INTERVAL_SECONDS:-86400}"

while true; do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)

  if pg_dump --format=custom --file="/backups/db-$stamp.dump.part"; then
    mv "/backups/db-$stamp.dump.part" "/backups/db-$stamp.dump"
    echo "backup: database saved to db-$stamp.dump"
  else
    rm -f "/backups/db-$stamp.dump.part"
    echo "backup: database dump FAILED" >&2
  fi

  if tar -czf "/backups/documents-$stamp.tar.gz.part" -C /documents .; then
    mv "/backups/documents-$stamp.tar.gz.part" "/backups/documents-$stamp.tar.gz"
    echo "backup: documents saved to documents-$stamp.tar.gz"
  else
    rm -f "/backups/documents-$stamp.tar.gz.part"
    echo "backup: documents copy FAILED" >&2
  fi

  find /backups -maxdepth 1 \( -name 'db-*.dump' -o -name 'documents-*.tar.gz' \) -mtime +"$keep" -delete
  sleep "$interval"
done
