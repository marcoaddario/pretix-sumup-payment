#!/bin/sh
# This runs as the pretix entrypoint's init script.
# Ensure /data is writable by the pretix user (UID 1000).
if [ -d /data ]; then
    chown -R 1000:1000 /data 2>/dev/null || chmod -R 777 /data
fi
