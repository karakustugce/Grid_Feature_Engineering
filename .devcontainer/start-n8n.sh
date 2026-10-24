#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${CODESPACE_NAME:-}" || -z "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  echo "This launcher is intended for GitHub Codespaces." >&2
  exit 1
fi

host="${CODESPACE_NAME}-5678.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
url="https://${host}"
image="${N8N_IMAGE:-docker.n8n.io/n8nio/n8n:latest}"

docker rm --force n8n >/dev/null 2>&1 || true
docker volume create n8n_data >/dev/null

docker run --detach \
  --name n8n \
  --restart unless-stopped \
  --publish 5678:5678 \
  --env N8N_HOST="${host}" \
  --env N8N_PORT=5678 \
  --env N8N_PROTOCOL=https \
  --env N8N_EDITOR_BASE_URL="${url}" \
  --env WEBHOOK_URL="${url}/" \
  --env N8N_PROXY_HOPS=1 \
  --env N8N_SECURE_COOKIE=true \
  --env N8N_DIAGNOSTICS_ENABLED=false \
  --env N8N_PERSONALIZATION_ENABLED=false \
  --volume n8n_data:/home/node/.n8n \
  "${image}" >/dev/null

echo "n8n Community Edition is starting at ${url}"
