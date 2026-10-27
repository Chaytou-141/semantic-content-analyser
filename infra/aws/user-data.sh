#!/usr/bin/env bash
set -euo pipefail
dnf install -y docker git openssl
systemctl enable --now docker
systemctl enable --now amazon-ssm-agent
mkdir -p /usr/local/lib/docker/cli-plugins /opt/semantic
COMPOSE_VERSION=v2.39.4
curl -fsSL "https://github.com/docker/compose/releases/download/$COMPOSE_VERSION/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
EXPECTED_SHA=7af95166a730b87e172d4fc9aefea8725d3c6c7327d59149267b452114ddb7d4
echo "$EXPECTED_SHA  /usr/local/lib/docker/cli-plugins/docker-compose" | sha256sum --check
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
