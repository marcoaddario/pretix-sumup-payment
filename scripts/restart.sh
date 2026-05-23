#!/bin/bash
set -euo pipefail

echo "Restarting pretix container..."
docker compose restart pretix
echo "Waiting for pretix to be ready..."
until curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health > /dev/null 2>&1; do
  sleep 1
done
echo "Pretix is ready."
