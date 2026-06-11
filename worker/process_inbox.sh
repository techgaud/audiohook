#!/usr/bin/env bash
# Render any unrendered EPUB in inbox/. Called by the inbox WatchPaths LaunchAgent when
# a file lands, or run by hand. Assumes the worker is up (org.audiohook.worker).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python orchestrator/pipeline.py --inbox
