#!/usr/bin/env python3
"""Render client: send a text chunk to the Kokoro worker, get back WAV audio.

Targets mlx-audio's built-in OpenAI-compatible server (mlx_audio.server):
    POST {worker_url}  {"model","input","voice","speed"}  ->  WAV bytes

Uses only the standard library so the Mac needs nothing beyond mlx-audio for the
worker. Lexicon inline overrides [word](/ipa/) are applied to the text by the caller
(see lexicon.apply) before it reaches here. Whether the server carries those overrides
through misaki end to end is the one open item to confirm on the Mac: if it does not,
switch the worker to the small custom worker that calls model.generate directly.
"""
import json
import time
import urllib.error
import urllib.request


def render_chunk(text, *, worker_url, model, voice, speed=1.0, timeout=180, retries=3):
    payload = json.dumps({
        "model": model, "input": text, "voice": voice, "speed": speed,
    }).encode("utf-8")
    req = urllib.request.Request(
        worker_url, data=payload, headers={"Content-Type": "application/json"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if not data:
                raise RuntimeError("empty audio response")
            return data
        except Exception as e:                       # noqa: BLE001 (network is flaky)
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"render failed after {retries} tries: {last}")


def health(worker_url, timeout=5):
    """Cheap reachability check against the worker host root."""
    base = worker_url.split("/v1/")[0]
    try:
        with urllib.request.urlopen(base, timeout=timeout) as r:
            return 200 <= r.status < 500
    except urllib.error.HTTPError:
        return True                                  # server answered, route just differs
    except Exception:
        return False


if __name__ == "__main__":
    # Smoke test against a running worker. Needs the Mac worker up:
    #   mlx_audio.server --host 127.0.0.1 --port 8000
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1/audio/speech"
    print("worker reachable:", health(url))
    wav = render_chunk("Hello from the audiohook pipeline.",
                       worker_url=url, model="mlx-community/Kokoro-82M-bf16", voice="am_michael")
    open("smoke.wav", "wb").write(wav)
    print(f"wrote smoke.wav ({len(wav)} bytes)")
