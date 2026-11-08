#!/bin/sh
# Install the locked development environment from this checkout.
set -eu
cd "$(dirname "$0")"
if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'Install uv from https://docs.astral.sh/uv/getting-started/installation/ first.' >&2
    exit 1
fi

uv sync --locked --extra dev
uv run --no-sync qrlp --version
printf '%s\n' 'Start the display with: uv run --no-sync qrlp live'
