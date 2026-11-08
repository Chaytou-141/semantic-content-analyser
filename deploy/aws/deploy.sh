#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ $# -ne 2 ]]; then
  echo "Usage: sudo bash deploy.sh ECR_IMAGE_URI DOMAIN" >&2
  exit 1
fi
IMAGE="$1"
DOMAIN="$2"
if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
  echo "Supply a DNS hostname such as analyser.example.com, not an IP or URL." >&2
  exit 1
fi
if [[ ! "$IMAGE" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[A-Za-z0-9._/@:-]+$ ]]; then
  echo "Supply an ECR image URI with a release tag or digest." >&2
  exit 1
fi
umask 077
if [[ ! -f .env ]]; then
  read -rsp "Choose a workspace password (16+ letters, numbers, underscores or hyphens): " WORKSPACE_PASSWORD
  echo
  if [[ ! "$WORKSPACE_PASSWORD" =~ ^[A-Za-z0-9_-]{16,}$ ]]; then
    echo "Password must contain 16+ letters, numbers, underscores or hyphens." >&2
    exit 1
  fi
  printf 'APP_PASSWORD=%s\nSECRET_KEY=%s\n' "$WORKSPACE_PASSWORD" "$(openssl rand -hex 32)" > .env
  unset WORKSPACE_PASSWORD
fi
printf 'IMAGE=%s\nDOMAIN=%s\n' "$IMAGE" "$DOMAIN" > release.env
docker compose --project-name semantic --env-file .env --env-file release.env -f compose.production.yaml pull
docker compose --project-name semantic --env-file .env --env-file release.env -f compose.production.yaml up -d --wait --wait-timeout 240
echo "Deployment started at https://$DOMAIN. Sign in with your workspace password."
