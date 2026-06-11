#!/usr/bin/env python3
"""Render driver (Mac): work/<slug>/chapters.json + lexicon -> library/<slug>.m4b.

Needs the Kokoro worker running (worker/start_worker.sh) and ffmpeg installed.
Resumable: an already-rendered chunk WAV is skipped, so a re-run continues where it
stopped, and deleting one chapter's audio folder re-renders just that chapter.

Flow per book:
  for each chapter:
    for each chunk:  apply lexicon -> render_chunk -> work/<slug>/audio/chNNN/chunkNNNN.wav
    concat chunk WAVs -> work/<slug>/audio/chNNN.wav
  assemble chapter WAVs -> library/<slug>.m4b  (chapters, title, author, optional cover)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import lexicon as lex_mod, render_client, assemble

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    path = os.path.join(ROOT, "config.toml")
    if tomllib and os.path.exists(path):
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def render_book(slug, cfg):
    paths = cfg.get("paths", {})
    work_root = os.path.join(ROOT, paths.get("work", "work"))
    lib_root = os.path.join(ROOT, paths.get("library", "library"))
    lex_path = os.path.join(ROOT, paths.get("lexicon", "lexicon/custom.json"))

    model = cfg.get("model", {}).get("id", "mlx-community/Kokoro-82M-bf16")
    voice = cfg.get("voice", {}).get("narrator", "am_michael")
    speed = cfg.get("voice", {}).get("speed", 1.0)
    worker_url = cfg.get("worker", {}).get("url", "http://127.0.0.1:8000/v1/audio/speech")

    bookdir = os.path.join(work_root, slug)
    chapters = json.load(open(os.path.join(bookdir, "chapters.json")))
    meta = json.load(open(os.path.join(bookdir, "meta.json")))
    lex = lex_mod.load(lex_path)

    if not render_client.health(worker_url):
        sys.exit(f"worker not reachable at {worker_url}\n"
                 f"start it with: worker/start_worker.sh  (then re-run)")

    audio_root = os.path.join(bookdir, "audio")
    os.makedirs(audio_root, exist_ok=True)
    chapter_wavs, titles = [], []

    for ch in chapters:
        cdir = os.path.join(audio_root, f"ch{ch['index']:03d}")
        os.makedirs(cdir, exist_ok=True)
        chunk_wavs = []
        for n, chunk in enumerate(ch["chunks"]):
            wpath = os.path.join(cdir, f"chunk{n:04d}.wav")
            if not (os.path.exists(wpath) and os.path.getsize(wpath) > 0):
                text = lex_mod.apply(chunk, lex)
                wav = render_client.render_chunk(
                    text, worker_url=worker_url, model=model, voice=voice, speed=speed)
                with open(wpath, "wb") as f:
                    f.write(wav)
            chunk_wavs.append(wpath)
        chwav = os.path.join(audio_root, f"ch{ch['index']:03d}.wav")
        assemble.concat_wavs(chunk_wavs, chwav)
        chapter_wavs.append(chwav)
        titles.append(ch["title"])
        print(f"  chapter {ch['index']:2d} {ch['title'][:24]:24s} "
              f"{len(chunk_wavs):3d} chunks -> {round(assemble.wav_duration(chwav)/60, 1)} min")

    os.makedirs(lib_root, exist_ok=True)
    out_m4b = os.path.join(lib_root, f"{slug}.m4b")
    cover = os.path.join(bookdir, "cover.jpg")
    assemble.to_m4b(chapter_wavs, titles, out_m4b,
                    title=meta.get("title", slug), author=meta.get("author", "Unknown"),
                    cover=cover if os.path.exists(cover) else None, workdir=audio_root)
    total = sum(assemble.wav_duration(w) for w in chapter_wavs)
    print(f"\ndone: {out_m4b}  ({len(chapter_wavs)} chapters, {round(total/3600, 2)} h)")
    return out_m4b


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "the-time-machine"
    render_book(slug, load_config())
