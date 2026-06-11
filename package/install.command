#!/usr/bin/env bash
# audiohook installer (macOS). Double-click from the mounted .dmg, or run from a checkout.
#
# Clones the orchestrator, sets up a Python venv with the render deps, points it at your
# content folders, and installs + loads the three LaunchAgents:
#   org.audiohook.worker  the Kokoro render worker (native Metal GPU)
#   org.audiohook.inbox   watches inbox/, renders a dropped EPUB
#   org.audiohook.pull    fast-forward-pulls the repo on an interval
#
# Re-runnable: a second run updates code and reloads the agents. Override with env vars
# AUDIOHOOK_HOME (default ~/audiohook) and AUDIOHOOK_REPO.
set -euo pipefail

REPO_URL="${AUDIOHOOK_REPO:-https://github.com/techgaud/audiohook.git}"
HOME_DIR="${AUDIOHOOK_HOME:-$HOME/audiohook}"
APP="$HOME_DIR/app"
INBOX="$HOME_DIR/inbox"
LIBRARY="$HOME_DIR/library"
AGENTS="$HOME/Library/LaunchAgents"

echo "==> audiohook install to $HOME_DIR"
mkdir -p "$HOME_DIR" "$INBOX" "$LIBRARY" "$AGENTS"

# 1) code: clone, or fast-forward an existing install
if [ -d "$APP/.git" ]; then
  git -C "$APP" pull --ff-only
else
  git clone "$REPO_URL" "$APP"
fi

# 2) system render deps via Homebrew
if ! command -v brew >/dev/null; then
  echo "Homebrew not found. Install it from https://brew.sh then re-run." >&2
  exit 1
fi
command -v ffmpeg    >/dev/null || brew install ffmpeg
command -v espeak-ng >/dev/null || brew install espeak-ng

# 3) python venv + deps (orchestrator front end + mlx-audio worker)
PY="$(command -v python3.11 || command -v python3)"
"$PY" -m venv "$APP/.venv"
V="$APP/.venv/bin"
"$V/python" -m pip install --upgrade pip >/dev/null
"$V/python" -m pip install -r "$APP/requirements.txt" mlx-audio
"$V/python" -m spacy download en_core_web_sm

# 4) point the app at the content folders (build-relative paths resolve through these)
ln -sfn "$INBOX" "$APP/inbox"
ln -sfn "$LIBRARY" "$APP/library"

# 5) LaunchAgents: fill the template placeholders with real paths, then load
for name in worker inbox pull; do
  dst="$AGENTS/org.audiohook.$name.plist"
  sed -e "s|/ABSOLUTE/PATH/TO/audiohook/build|$APP|g" \
      -e "s|/ABSOLUTE/PATH/TO/venv/bin|$V|g" \
      -e "s|/ABSOLUTE/PATH/TO/inbox|$INBOX|g" \
      "$APP/worker/launchd/org.audiohook.$name.plist" > "$dst"
  launchctl unload "$dst" 2>/dev/null || true
  launchctl load "$dst"
done

echo "==> done. Drop EPUBs in $INBOX ; M4Bs appear in $LIBRARY"
echo "    worker, inbox watcher, and code puller are loaded."
echo "    logs: /tmp/audiohook-*.log"
