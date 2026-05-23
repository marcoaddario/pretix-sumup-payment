#!/bin/bash
set -euo pipefail

echo "Following pretix logs (Ctrl+C to stop)..."
docker compose logs -f pretix
