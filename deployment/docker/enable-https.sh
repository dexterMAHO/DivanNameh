#!/usr/bin/env bash
set -euo pipefail

deploy_root=${DIVAN_DEPLOY_ROOT:-/opt/divannameh}
release="$deploy_root/current"
settings="$release/compose.env"

if [[ ! -r "$settings" || ! -r "$deploy_root/secrets.env" || ! -r "$release/compose.yaml" ]]; then
    printf 'Cannot read the deployed Compose files under %s. Run as root on the VPS.\n' "$release" >&2
    exit 1
fi

domain=$(sed -n 's/^DIVAN_DOMAIN=//p' "$settings")
if [[ ! "$domain" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z0-9-]+$ ]]; then
    printf 'Invalid DIVAN_DOMAIN in %s\n' "$settings" >&2
    exit 1
fi

cd "$release"
compose=(docker compose --project-name divannameh
    --env-file "$deploy_root/secrets.env" --env-file "$settings")

running=$("${compose[@]}" ps --status running --quiet proxy)
if [[ -z "$running" ]]; then
    "${compose[@]}" up --detach --no-deps proxy
fi

published=$("${compose[@]}" port proxy 443)
port=${published##*:}
address=${published%:*}
case "$address" in
    0.0.0.0) address=127.0.0.1 ;;
    '[::]') address='[::1]' ;;
esac
if [[ -z "$address" || ! "$port" =~ ^[0-9]+$ ]]; then
    printf 'Caddy does not have a published HTTPS port.\n' >&2
    exit 1
fi

check_https() {
    curl --fail --silent --show-error --connect-timeout 4 --max-time 8 \
        --noproxy "$domain" --connect-to "$domain:443:$address:$port" \
        --output /dev/null --write-out '%{http_code}' "https://$domain/healthz/"
}

if response=$(check_https 2>/dev/null) && [[ "$response" == 200 ]]; then
    printf 'Origin HTTPS is already active for %s (HTTP 200, trusted certificate).\n' "$domain"
    exit 0
fi

config=/etc/caddy/Caddyfile
"${compose[@]}" exec -T proxy caddy validate --config "$config" --adapter caddyfile
"${compose[@]}" exec -T proxy caddy reload --config "$config" --adapter caddyfile

# ACME issuance may complete after the reload returns.
for attempt in {1..12}; do
    if response=$(check_https 2>/dev/null) && [[ "$response" == 200 ]]; then
        printf 'Origin HTTPS is active for %s (HTTP 200, trusted certificate).\n' "$domain"
        exit 0
    fi
    if (( attempt < 12 )); then
        sleep 5
    fi
done

printf 'Could not verify origin HTTPS for %s. Check DNS and inbound ports 80/443.\n' "$domain" >&2
check_https >&2 || true
"${compose[@]}" logs --tail=50 proxy >&2
exit 1
