#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> git pull"
git pull --ff-only

echo "==> build frontends"
(cd frontend && pnpm install --frozen-lockfile && pnpm build)

echo "==> rebuild + restart api"
docker compose build api
docker compose up -d db api nginx backup

echo "==> run migrations"
docker compose exec -T api alembic upgrade head

echo "==> done. current versions:"
docker compose ps
