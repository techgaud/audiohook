#!/usr/bin/env python3
"""Phase C: pronunciation review. Hear a proposed pronunciation, confirm, lexiconize.

The reviewer confirms a name by EAR, not by reading IPA. The loop:

  1. prepare.py wrote work/<slug>/review.json (candidates, "ipa": null).
  2. Propose an IPA for the candidates worth fixing: set the "ipa" field. Claude does
     this best-guess pass, or you do.
  3. review.py samples <slug>
       For each candidate that has an ipa, renders an A/B pair from a real sentence in
       the book, into work/<slug>/review_samples/:
         <word>__proposed.wav   with the [word](/ipa/) override
         <word>__default.wav    espeak's guess, for comparison
       Listen. Set "approved": true on the ones that sound right (edit review.json).
  4. review.py commit <slug>
       Merges approved candidates into lexicon/custom.json and deletes the audio of any
       chapter that uses them, so render.py re-renders only those chapters.

samples needs the worker (Mac). commit is offline.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import lexicon as lex_mod, render_client

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SENT = re.compile(r'[^.!?]*[.!?]')


def load_config():
    path = os.path.join(ROOT, "config.toml")
    if tomllib and os.path.exists(path):
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def _paths(cfg, slug):
    p = cfg.get("paths", {})
    bookdir = os.path.join(ROOT, p.get("work", "work"), slug)
    return bookdir, os.path.join(ROOT, p.get("lexicon", "lexicon/custom.json"))


def example_sentence(chapters, word, maxlen=240):
    """A real sentence from the book containing word, for an authentic-sounding sample."""
    pat = re.compile(rf"\b{re.escape(word)}\b", re.I)
    for ch in chapters:
        for chunk in ch["chunks"]:
            if not pat.search(chunk):
                continue
            for sent in _SENT.findall(chunk):
                if pat.search(sent) and len(sent.strip()) <= maxlen:
                    return sent.strip()
    return f"The name is {word}."


def samples(slug, cfg):
    bookdir, _ = _paths(cfg, slug)
    review = json.load(open(os.path.join(bookdir, "review.json")))
    chapters = json.load(open(os.path.join(bookdir, "chapters.json")))
    todo = [c for c in review if c.get("ipa")]
    if not todo:
        sys.exit("no candidates have a proposed ipa yet (fill the 'ipa' field in review.json)")

    model = cfg.get("model", {}).get("id", "mlx-community/Kokoro-82M-bf16")
    voice = cfg.get("voice", {}).get("narrator", "am_michael")
    speed = cfg.get("voice", {}).get("speed", 1.0)
    worker_url = cfg.get("worker", {}).get("url", "http://127.0.0.1:8000/v1/audio/speech")
    if not render_client.health(worker_url):
        sys.exit(f"worker not reachable at {worker_url} (start worker/start_worker.sh)")

    outdir = os.path.join(bookdir, "review_samples")
    os.makedirs(outdir, exist_ok=True)
    for c in todo:
        word, ipa = c["word"], c["ipa"]
        sent = example_sentence(chapters, word)
        variants = {"default": sent, "proposed": lex_mod.apply(sent, {word.lower(): ipa})}
        for tag, text in variants.items():
            wav = render_client.render_chunk(
                text, worker_url=worker_url, model=model, voice=voice, speed=speed)
            with open(os.path.join(outdir, f"{word}__{tag}.wav"), "wb") as f:
                f.write(wav)
        print(f"  {word:16s} /{ipa}/   \"{sent[:60]}\"")
    print(f"\nlisten in {outdir}/  (compare __proposed vs __default), then set "
          f"\"approved\": true in review.json and run: review.py commit {slug}")


def commit(slug, cfg):
    bookdir, lex_path = _paths(cfg, slug)
    review = json.load(open(os.path.join(bookdir, "review.json")))
    chapters = json.load(open(os.path.join(bookdir, "chapters.json")))
    approved = [c for c in review if c.get("approved") and c.get("ipa")]
    if not approved:
        sys.exit("nothing approved (set \"approved\": true on confirmed candidates)")

    lex = lex_mod.load(lex_path)
    for c in approved:
        lex[c["word"].lower()] = c["ipa"]
    lex_mod.save(lex_path, lex)

    # re-render only chapters that use a newly approved word
    pats = [re.compile(rf"\b{re.escape(c['word'])}\b", re.I) for c in approved]
    affected = []
    for ch in chapters:
        text = " ".join(ch["chunks"])
        if any(p.search(text) for p in pats):
            affected.append(ch["index"])
            cdir = os.path.join(bookdir, "audio", f"ch{ch['index']:03d}")
            shutil.rmtree(cdir, ignore_errors=True)
            chwav = os.path.join(bookdir, "audio", f"ch{ch['index']:03d}.wav")
            if os.path.exists(chwav):
                os.remove(chwav)

    print(f"added {len(approved)} entries to {os.path.relpath(lex_path, ROOT)}: "
          f"{', '.join(c['word'] for c in approved)}")
    print(f"cleared audio for {len(affected)} affected chapter(s): {affected}")
    print(f"re-render with: python orchestrator/render.py {slug}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("samples", "commit"):
        sys.exit("usage: review.py {samples|commit} <slug>")
    cmd, slug = sys.argv[1], sys.argv[2]
    (samples if cmd == "samples" else commit)(slug, load_config())
