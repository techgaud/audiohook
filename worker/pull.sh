#!/usr/bin/env bash
# Track the orchestrator repo. Called on an interval by the pull LaunchAgent so the Mac
# always runs the latest code. One-directional: the Mac only ever fast-forward-pulls.
set -euo pipefail
cd "$(dirname "$0")"/..
git pull --ff-only
