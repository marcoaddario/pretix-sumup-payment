#!/bin/sh
set -e

# Fix permissions on the data volume (mounted at /data)
if [ -d /data ]; then
    chmod -R 777 /data 2>/dev/null || true
fi

# Find and run the original pretix entrypoint
# The standalone image's entrypoint generates production_settings.py and more
for entrypoint in \
    /entrypoint.sh \
    /docker-entrypoint.sh \
    /usr/local/bin/docker-entrypoint.sh \
    /usr/local/bin/entrypoint.sh \
    /docker-entrypoint \
    /entrypoint; do
    if [ -x "$entrypoint" ]; then
        exec "$entrypoint" "$@"
    fi
done

# Fallback: try the pretix CLI directly (bypasses entrypoint setup)
echo "No entrypoint found, running pretix directly" >&2
exec pretix "$@"
