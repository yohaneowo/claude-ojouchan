#!/bin/sh
# Start or restart Claude-Ojouchan on the VM: write the settings from Doppler, then start AstrBot.
# Run as root from /opt/ojouchan. The Doppler service token (read-only, claude-ojouchan/prd) lives in
# /etc/ojouchan/doppler-token.
set -e
cd "$(dirname "$0")/.."
DOPPLER_TOKEN="$(cat /etc/ojouchan/doppler-token)"
export DOPPLER_TOKEN
docker compose stop astrbot >/dev/null 2>&1 || true
doppler run --no-check-version -- sh -c 'python3 deploy/configure.py data/cmd_config.json && docker compose up -d --force-recreate'
