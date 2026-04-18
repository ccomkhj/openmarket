# TLS on the LAN — Self-Signed Certificate Setup

Goal: the cashier tablet and admin laptop speak HTTPS to the NUC over the LAN
without browser warnings. We use a self-signed root CA and per-hostname certs
for `admin.local`, `pos.local`, `store.local`.

## On the NUC — generate root CA once

    mkdir -p /etc/openmarket/tls && cd /etc/openmarket/tls
    openssl genrsa -out rootCA.key 4096
    openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 3650 \
        -out rootCA.crt -subj "/CN=OpenMarket LAN Root CA"

## Generate server cert signed by the root CA

    cat > san.cnf <<EOF
    [req]
    distinguished_name=req
    [san]
    subjectAltName=DNS:admin.local,DNS:pos.local,DNS:store.local
    EOF
    openssl genrsa -out server.key 2048
    openssl req -new -key server.key -out server.csr \
        -subj "/CN=openmarket.local"
    openssl x509 -req -in server.csr -CA rootCA.crt -CAkey rootCA.key \
        -CAcreateserial -out server.crt -days 825 -sha256 \
        -extfile san.cnf -extensions san

## Wire into nginx

Edit `/etc/nginx/nginx.conf`:

    server {
        listen 443 ssl;
        server_name admin.local pos.local store.local;
        ssl_certificate     /etc/openmarket/tls/server.crt;
        ssl_certificate_key /etc/openmarket/tls/server.key;
        # ... existing proxy_pass config ...
    }
    server {
        listen 80;
        return 301 https://$host$request_uri;
    }

Reload: `docker compose exec nginx nginx -s reload`

## LAN DNS — /etc/hosts on each device

On the tablet and admin laptop, add to `/etc/hosts` (or equivalent):

    192.168.1.10  admin.local pos.local store.local

(Replace `192.168.1.10` with the NUC's LAN IP.)

## Install the root CA on each device

Copy `rootCA.crt` to each device (USB drive or scp). Then:

- **macOS:** Keychain Access → System → drag `rootCA.crt` in → set Trust: Always Trust.
- **Windows:** double-click `rootCA.crt` → Install Certificate → Local Machine → Place in "Trusted Root Certification Authorities".
- **iPadOS/iOS:** email the CA to yourself → tap → Settings → Profile Downloaded → Install → Settings → General → About → Certificate Trust Settings → enable.
- **Android:** Settings → Security → Install from storage → select `rootCA.crt` → CA certificate.
- **Linux:** `sudo cp rootCA.crt /usr/local/share/ca-certificates/openmarket-root.crt && sudo update-ca-certificates`

## Verify

From each device, visit `https://admin.local` — no warning, padlock green.

## Renewal

The server cert is valid 825 days (Apple/Chrome cap). Calendar a renewal one
month before expiry. Re-run the "generate server cert" step and reload nginx.
The root CA is valid 10 years.
