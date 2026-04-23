#!/usr/bin/env bash
# End-to-end smoke test. Runs against a live stack.
#
# Usage:
#   ./scripts/smoke-test.sh                 # assumes https://localhost
#   BASE=https://openmarket.local ./scripts/smoke-test.sh
#
# Exits 0 on success, non-zero on first failure.
#
# Requires: curl, jq. Requires bootstrap already done (first owner created).
# Needs OWNER_EMAIL + OWNER_PASSWORD in env or .env.smoke.

set -euo pipefail

BASE="${BASE:-https://localhost}"
CURL=(curl -sS -k -c /tmp/smoke-cookies.txt -b /tmp/smoke-cookies.txt)

if [[ -f .env.smoke ]]; then
  # shellcheck disable=SC1091
  . .env.smoke
fi
: "${OWNER_EMAIL:?set OWNER_EMAIL in env or .env.smoke}"
: "${OWNER_PASSWORD:?set OWNER_PASSWORD in env or .env.smoke}"

rm -f /tmp/smoke-cookies.txt

step() { echo; echo "==> $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

step "health"
"${CURL[@]}" "$BASE/api/health" | jq -e '.status == "ok"' >/dev/null || fail "health"

step "store-info"
"${CURL[@]}" "$BASE/api/store-info" | jq -e '.merchant_name' >/dev/null || fail "store-info"

step "login as owner"
"${CURL[@]}" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg e "$OWNER_EMAIL" --arg p "$OWNER_PASSWORD" '{email:$e,password:$p}')" \
  -X POST "$BASE/api/auth/login" | jq -e '.id' >/dev/null || fail "login"

step "list products"
"${CURL[@]}" "$BASE/api/products?limit=1" | jq -e 'type == "array"' >/dev/null || fail "products list"

step "list orders"
"${CURL[@]}" "$BASE/api/orders?limit=1" | jq -e 'type == "array"' >/dev/null || fail "orders list"

step "analytics (1d)"
"${CURL[@]}" "$BASE/api/analytics/summary?days=1" | jq -e '.total_orders != null' >/dev/null || fail "analytics"

step "low-stock count"
"${CURL[@]}" "$BASE/api/inventory-levels/low-stock-count?location_id=1" | jq -e '.count != null' >/dev/null || fail "low-stock"

step "printer health"
"${CURL[@]}" "$BASE/api/health/printer" | jq -e '.online != null' >/dev/null || fail "printer health"

step "terminal health"
"${CURL[@]}" "$BASE/api/health/terminal" | jq -e '.online != null' >/dev/null || fail "terminal health"

step "fiskaly health"
"${CURL[@]}" "$BASE/api/health/fiskaly" | jq -e '.online != null' >/dev/null || fail "fiskaly health"

step "logout"
"${CURL[@]}" -X POST "$BASE/api/auth/logout" >/dev/null

echo
echo "ALL OK"
