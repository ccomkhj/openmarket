#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$(dirname "$0")/../certs"
mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/server.crt" && -f "$CERT_DIR/server.key" ]]; then
  echo "cert already exists in $CERT_DIR — delete files there to regenerate"
  exit 0
fi

CN="${1:-openmarket.local}"
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1"

echo "wrote $CERT_DIR/server.crt (CN=$CN)"
echo "install $CERT_DIR/server.crt in each client browser/keychain to avoid warnings"
