#!/usr/bin/env bash
# Kokoro render worker: mlx-audio's OpenAI-compatible TTS server.
# Run NATIVE on macOS (not in a container) so MLX gets the Metal GPU.
#
#   brew install ffmpeg espeak-ng
#   pip install mlx-audio misaki num2words
#   ./worker/start_worker.sh
#
# Endpoint: POST http://HOST:PORT/v1/audio/speech  {"model","input","voice","speed"}
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if command -v mlx_audio.server >/dev/null 2>&1; then
  exec mlx_audio.server --host "$HOST" --port "$PORT"
else
  exec python -m mlx_audio.server --host "$HOST" --port "$PORT"
fi
