# Backup & Restore

## Where backups live

Every 24h the `backup` service writes a gzipped `pg_dump` to `./backups/`.
The last **14** files are kept; older are deleted automatically.

```
backups/openmarket-2026-04-23T02-00-00Z.sql.gz
backups/openmarket-2026-04-22T02-00-00Z.sql.gz
...
```

Replicate `./backups/` off-box (USB drive, NAS, `rsync` in a system cron).
Losing the NUC's disk would otherwise take the backups with it.

## Manual backup (before risky ops)

```bash
docker compose exec backup /backup.sh
```

## Restore

1. Stop the api so nothing writes during restore:

   ```bash
   docker compose stop api
   ```

2. Wipe the live database and recreate it empty:

   ```bash
   docker compose exec db psql -U openmarket -d postgres \
     -c "DROP DATABASE openmarket;" -c "CREATE DATABASE openmarket;"
   ```

3. Pipe the chosen dump back in:

   ```bash
   gunzip -c backups/openmarket-2026-04-23T02-00-00Z.sql.gz \
     | docker compose exec -T db psql -U openmarket -d openmarket
   ```

4. Start the api again:

   ```bash
   docker compose start api
   ```

5. Verify by loading admin, checking a recent order, and ringing up a
   1-cent test sale.
