#!/usr/bin/env python3
"""Sentence-aware chunking under the Kokoro token ceiling.

Kokoro processes a bounded number of phoneme tokens per call (near 510, confirmed
on the Mac). We do not have phonemes at chunk time, so we use a character budget as
a safe proxy and keep whole sentences together. Sentences longer than the budget are
hard-split at clause boundaries, then at word boundaries as a last resort.

Per-chapter chunking matters: a single bad chunk re-renders one chapter, not the book.
"""
import re

# Split after sentence-final punctuation when followed by whitespace and a likely
# sentence start. Abbreviations are mostly expanded by text_normalize first.
_SENT = re.compile(r'(?<=[.!?])["\']?\s+(?=["\'(\[]?[A-Z0-9])')
_CLAUSE = re.compile(r'(?<=[,;:])\s+')


def split_sentences(text):
    out = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        out.extend(s.strip() for s in _SENT.split(para) if s.strip())
    return out


def _hard_split(sentence, budget):
    pieces, cur = [], ""
    units = _CLAUSE.split(sentence)
    if max((len(u) for u in units), default=0) > budget:
        units = sentence.split(" ")           # fall back to words
    for u in units:
        cand = (cur + " " + u).strip()
        if len(cand) > budget and cur:
            pieces.append(cur)
            cur = u
        else:
            cur = cand
    if cur:
        pieces.append(cur)
    return pieces


def chunk_text(text, budget=500):
    chunks, cur = [], ""
    for sent in split_sentences(text):
        if len(sent) > budget:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(_hard_split(sent, budget))
            continue
        cand = (cur + " " + sent).strip()
        if len(cand) > budget and cur:
            chunks.append(cur)
            cur = sent
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    return chunks


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from orchestrator import epub_to_chapters, text_normalize
    chs = epub_to_chapters.body_chapters("tests/fixtures/the-time-machine.epub")
    total = 0
    for c in chs:
        chunks = chunk_text(text_normalize.normalize(c["text"]), budget=500)
        total += len(chunks)
        longest = max((len(x) for x in chunks), default=0)
        print(f"  ch {c['index']:2d} {c['title'][:8]:8s}: {len(chunks):3d} chunks, longest {longest} chars")
    print(f"\ntotal chunks across {len(chs)} chapters: {total}")
