#!/usr/bin/env bash
set -euo pipefail
umask 077

if (( $# < 2 )); then
    printf 'Usage: %s SERVER DOMAIN [ANSIBLE_OPTIONS...]\n' "$0" >&2
    exit 2
fi

server=$1
domain=$2
shift 2

if [[ ! $server =~ ^[a-zA-Z0-9:][a-zA-Z0-9.:-]*$ ||
      ! $domain =~ ^[a-zA-Z0-9][a-zA-Z0-9-]*(\.[a-zA-Z0-9][a-zA-Z0-9-]*)+$ ]]; then
    printf 'Provide a server IP or SSH hostname and a separate DNS domain.\n' >&2
    exit 2
fi

for dependency in ansible-playbook openssl; do
    if ! command -v "$dependency" >/dev/null; then
        printf 'Required command is missing: %s\n' "$dependency" >&2
        exit 1
    fi
done

ansible_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
inventory=$(mktemp "$ansible_dir/.env.inventory.XXXXXX.yml")
trap 'unlink "$inventory"' EXIT
secrets_file="$ansible_dir/../../.env.deploy-root"

if [[ ! -e $secrets_file ]]; then
    read -r -s -p 'PostgreSQL password for a fresh install: ' db_password
    printf '\n'
    if [[ ! $db_password =~ ^[a-zA-Z0-9_-]+$ ]]; then
        printf 'Use a password with letters, digits, underscores or hyphens.\n' >&2
        exit 2
    fi
    secret_key=$(openssl rand -hex 48)
    (
        set -o noclobber
        printf 'DIVAN_SECRET_KEY=%s\nDIVAN_DB_PASSWORD=%s\n' \
            "$secret_key" "$db_password" > "$secrets_file"
    )
    unset db_password secret_key
fi

chmod 600 "$secrets_file"
cat > "$inventory" <<INVENTORY
all:
  children:
    divan_servers:
      hosts:
        divan:
          ansible_host: "$server"
          ansible_user: root
          ansible_port: 9011
          ansible_become: false
          divan_domain: "$domain"
INVENTORY

ssh_password_file="$ansible_dir/../../.env.ssh-root"
ssh_options=()
if [[ -f $ssh_password_file ]]; then
    chmod 600 "$ssh_password_file"
    ssh_options+=(--extra-vars "@$ssh_password_file")
fi

DIVAN_SECRETS_FILE="$secrets_file" \
    ansible-playbook -i "$inventory" "$ansible_dir/deploy.yml" "${ssh_options[@]}" "$@"
