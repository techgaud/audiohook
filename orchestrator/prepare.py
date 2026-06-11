#!/usr/bin/env python3
"""Driver: EPUB in -> render-ready artifacts out.

Runs the platform-agnostic front of the pipeline and writes, under work/<slug>/:
  meta.json      book title, author, chapter and chunk counts
  chapters.json  normalized, chunked body chapters [{index, title, chunks: [...]}]
  review.json    pronunciation-review candidates [{word, count, label, zipf, ipa}]
  review.md      the same list, human-readable, for filling in IPA

The render step (macOS, mlx-audio) reads chapters.json, applies the lexicon, and sends
chunks to the Kokoro worker. The review step fills review.json IPA values into
lexicon/custom.json.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import epub_to_chapters, text_normalize, chunk, oov_scan

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


def _config():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml")
    if tomllib and os.path.exists(path):
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def _meta(path):
    from ebooklib import epub
    book = epub.read_epub(path)

    def first(ns, name):
        v = book.get_metadata(ns, name)
        return v[0][0] if v else None
    return first("DC", "title") or os.path.basename(path), first("DC", "creator") or "Unknown"


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "book"


def prepare(epub_path, out_root="work"):
    cfg = _config()
    budget = cfg.get("model", {}).get("max_chunk_chars", 500)
    thresh = cfg.get("oov", {}).get("rare_zipf_threshold", 2.5)
    min_count = cfg.get("oov", {}).get("min_count", 1)

    title, author = _meta(epub_path)
    slug = _slug(title)
    out = os.path.join(out_root, slug)
    os.makedirs(out, exist_ok=True)

    chapters = epub_to_chapters.body_chapters(epub_path)
    for c in chapters:
        c["text"] = text_normalize.normalize(c["text"])

    chunked, n_chunks = [], 0
    for c in chapters:
        chunks = chunk.chunk_text(c["text"], budget=budget)
        n_chunks += len(chunks)
        chunked.append({"index": c["index"], "title": c["title"], "chunks": chunks})

    review = oov_scan.scan(chapters, rare_zipf_threshold=thresh, min_count=min_count)

    meta = {"title": title, "author": author, "slug": slug,
            "source": os.path.basename(epub_path),
            "n_chapters": len(chapters), "n_chunks": n_chunks,
            "n_review_candidates": len(review)}
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=2)
    json.dump(chunked, open(os.path.join(out, "chapters.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(review, open(os.path.join(out, "review.json"), "w"), ensure_ascii=False, indent=1)

    with open(os.path.join(out, "review.md"), "w") as f:
        f.write(f"# Pronunciation review: {title} ({author})\n\n")
        f.write("Fill the IPA column for any name or word that should not be left to espeak. "
                "Confirm by hearing a sample on the Mac, then it goes into lexicon/custom.json.\n\n")
        f.write("| word | count | label | zipf | IPA |\n|---|---|---|---|---|\n")
        for r in review:
            f.write(f"| {r['word']} | {r['count']} | {r['label']} | {r['zipf']} |  |\n")

    return meta, out


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/the-time-machine.epub"
    meta, out = prepare(p)
    print(f"prepared: {meta['title']} ({meta['author']})")
    print(f"  {meta['n_chapters']} chapters, {meta['n_chunks']} chunks, "
          f"{meta['n_review_candidates']} review candidates")
    print(f"  artifacts in {out}/  (meta.json, chapters.json, review.json, review.md)")
