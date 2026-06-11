# audiohook

Turn a DRM-free EPUB into a single-narrator audiobook (M4B) with Kokoro TTS
(mlx-audio) on Apple Silicon.

This repo is the orchestrator: the platform-agnostic front of the pipeline. It parses
the EPUB, normalizes text, splits each chapter into sentence-aligned chunks under the
Kokoro token limit, scans for out-of-vocabulary words that need a pronunciation review,
and manages a custom IPA lexicon that is injected as misaki inline overrides at render
time. The Kokoro render worker runs natively on macOS for Metal GPU access.

## Install

    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    python -m spacy download en_core_web_sm

## Use

    python orchestrator/prepare.py path/to/book.epub

Writes `work/<slug>/`:
- `chapters.json` normalized, chunked body chapters
- `review.json` / `review.md` pronunciation-review candidates (names and rare words), ranked
- `meta.json` title, author, chapter and chunk counts

Fill IPA for any candidate in the review file, add it to `lexicon/custom.json`
(word to IPA), and it pronounces correctly on every render.

## Pronunciation review

Names and rare words espeak would mispronounce are listed in `work/<slug>/review.json`
and `review.md`, ranked names-first. Propose an IPA for the ones worth fixing (set the
`ipa` field), then confirm by ear:

    python orchestrator/review.py samples <slug>   # renders A/B: proposed vs default
    # listen in work/<slug>/review_samples/, set "approved": true on the good ones
    python orchestrator/review.py commit <slug>     # -> lexicon/custom.json, re-render affected chapters

`commit` adds approved entries to the lexicon and clears the audio of only the chapters
that use them, so the next render redoes just those. The lexicon persists across books.

## Render (macOS)

The render worker runs natively on macOS so Kokoro gets the Metal GPU (containers
cannot reach Metal). Install once:

    brew install ffmpeg espeak-ng
    pip install mlx-audio misaki num2words

Start the worker, then render a prepared book:

    ./worker/start_worker.sh                     # mlx-audio server on :8000
    python orchestrator/render.py <slug>         # work/<slug> -> library/<slug>.m4b

Rendering is resumable (already-rendered chunks are skipped) and produces a chaptered
M4B with title, author, and an optional `work/<slug>/cover.jpg`. For an always-on
worker, install the LaunchAgent in `worker/launchd/`.

## Modules

| module | does |
|---|---|
| `epub_to_chapters.py` | EPUB to ordered body chapters, drops front/back matter and note markers |
| `text_normalize.py` | encoding fixes, punctuation unification, safe abbreviation expansion |
| `chunk.py` | sentence-aware chunking under the Kokoro token ceiling |
| `oov_scan.py` | pronunciation-review candidates via misaki lexicon, spaCy NER, wordfreq |
| `lexicon.py` | custom word to IPA, emitted as misaki inline overrides |
| `prepare.py` | driver: EPUB in, render-ready artifacts out |
| `render_client.py` | send a chunk to the Kokoro worker, get WAV back |
| `assemble.py` | concat chunk WAVs to chapters, then a chaptered M4B (ffmpeg) |
| `render.py` | driver: prepared book + lexicon -> library/<slug>.m4b |
| `review.py` | pronunciation review: sample A/B, confirm by ear, lexiconize |
