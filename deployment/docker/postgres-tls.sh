#!/bin/sh
set -eu

# The production Django settings require TLS even on a private Compose network.
cert_dir=$(mktemp -d)
openssl req -new -x509 -nodes -days 365 -subj /CN=db \
    -keyout "$cert_dir/server.key" -out "$cert_dir/server.crt" >/dev/null 2>&1
chmod 600 "$cert_dir/server.key"
chown -R postgres:postgres "$cert_dir"

# The administrative role is accessed locally through docker compose exec.
export POSTGRES_PASSWORD="$(openssl rand -hex 32)"

exec docker-entrypoint.sh postgres \
    -c ssl=on \
    -c "ssl_cert_file=$cert_dir/server.crt" \
    -c "ssl_key_file=$cert_dir/server.key"
