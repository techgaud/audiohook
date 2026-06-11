#!/usr/bin/env python3
"""Full book pipeline and inbox automation: EPUB in -> M4B out.

  process_epub(path)  prepare (parse, normalize, chunk, OOV scan) then render (Kokoro -> M4B)
  process_inbox()     render every EPUB in inbox/ that has no M4B in library/ yet

A watcher (a macOS WatchPaths LaunchAgent, see worker/launchd/) calls process_inbox when
an EPUB lands. Idempotent: an already-rendered book is skipped, so re-runs are cheap and
a half-finished render resumes (render.py skips chunks it already made).

Note: the pronunciation review step is intentionally manual. Auto-rendering an unreviewed
book is fine for a first listen; rerun review.py + render.py to refine pronunciations.
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import prepare, render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _roots(cfg):
    p = cfg.get("paths", {})
    return (os.path.join(ROOT, p.get("inbox", "inbox")),
            os.path.join(ROOT, p.get("library", "library")),
            os.path.join(ROOT, p.get("work", "work")))


def process_epub(epub_path, cfg=None):
    cfg = cfg or render.load_config()
    _, _, work_root = _roots(cfg)
    meta, _ = prepare.prepare(epub_path, out_root=work_root)
    print(f"prepared {meta['title']}: {meta['n_chapters']} chapters, "
          f"{meta['n_chunks']} chunks, {meta['n_review_candidates']} review candidates")
    return render.render_book(meta["slug"], cfg)


def process_inbox(cfg=None):
    cfg = cfg or render.load_config()
    inbox, library, _ = _roots(cfg)
    if not os.path.isdir(inbox):
        sys.exit(f"no inbox at {inbox}")
    done, skipped = [], []
    for epub in sorted(glob.glob(os.path.join(inbox, "*.epub"))):
        title = prepare._meta(epub)[0]
        slug = prepare._slug(title)
        if os.path.exists(os.path.join(library, f"{slug}.m4b")):
            skipped.append(slug)
            continue
        process_epub(epub, cfg)
        done.append(slug)
    print(f"\ninbox: rendered {len(done)} ({', '.join(done) or 'none'}), "
          f"skipped {len(skipped)} already done")
    return done


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--inbox":
        process_inbox()
    elif len(sys.argv) > 1:
        process_epub(sys.argv[1])
    else:
        sys.exit("usage: pipeline.py <book.epub> | pipeline.py --inbox")
