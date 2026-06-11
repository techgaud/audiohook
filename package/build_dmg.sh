#!/usr/bin/env bash
# Build audiohook-installer.dmg (macOS). The image carries the installer, which clones
# the repo and sets everything up. Uses only the built-in hdiutil, no extra tooling.
#
#   ./package/build_dmg.sh [out.dmg]
set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-audiohook-installer.dmg}"
STAGE="$(mktemp -d)/audiohook"
mkdir -p "$STAGE"

cp install.command "$STAGE/Install audiohook.command"
chmod +x "$STAGE/Install audiohook.command"
[ -f README.md ] && cp README.md "$STAGE/README.md"

rm -f "$OUT"
hdiutil create -volname "audiohook" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "built $OUT"

# Optional, for a Gatekeeper-clean image (needs an Apple Developer ID):
#   codesign --force --sign "Developer ID Application: NAME (TEAMID)" "$OUT"
#   xcrun notarytool submit "$OUT" --keychain-profile NOTARY --wait
#   xcrun stapler staple "$OUT"
