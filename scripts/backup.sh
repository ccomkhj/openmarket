#!/usr/bin/env sh
set -eu

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT="/backups/openmarket-$STAMP.sql.gz"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip -9 > "$OUT"
echo "wrote $OUT"

ls -1t /backups/openmarket-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
