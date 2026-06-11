#!/usr/bin/env python3
"""EPUB -> ordered list of body chapters (title + clean text).

Reads the spine in reading order, parses each XHTML doc, drops footnote/endnote
reference markers (so they are not read aloud), and classifies front/back matter
(titlepage, imprint, colophon, toc, etc.) so the default output is just the body.

Returns a list of dicts: {index, id, kind, title, text}.
kind is one of: body | frontmatter | backmatter.
"""
import os
import sys

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# epub:type values that mark non-body sections we skip by default.
SKIP_TYPES = {
    "titlepage", "halftitlepage", "imprint", "colophon", "copyright-page",
    "cover", "toc", "frontmatter-toc", "loi", "lot", "dedication", "epigraph",
    "acknowledgements", "endnotes", "footnotes", "uncopyright", "appendix-toc",
}
SKIP_NAME_HINTS = ("titlepage", "halftitle", "imprint", "colophon", "copyright",
                   "cover", "toc", "nav", "dedication", "epigraph", "uncopyright",
                   "endnotes", "footnotes", "loi", "lot")
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "li"]


def _section_type(soup):
    el = soup.find(attrs={"epub:type": True}) or soup.find("body")
    return (el.get("epub:type", "") if el else "").lower()


def _classify(name, sec_type):
    n = name.lower()
    types = set(sec_type.split())
    if types & SKIP_TYPES or any(h in n for h in SKIP_NAME_HINTS):
        # distinguish front vs back loosely by common naming
        if any(b in n for b in ("colophon", "uncopyright", "endnotes", "appendix", "afterword")):
            return "backmatter"
        return "frontmatter"
    return "body"


def _title(soup, fallback):
    for tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        h = soup.find(tag)
        if h and h.get_text(strip=True):
            return h.get_text(" ", strip=True)
    return fallback


def _text(soup):
    body = soup.find("body") or soup
    # drop note reference anchors and superscript markers so they are not voiced
    for a in body.find_all("a"):
        if "noteref" in (a.get("epub:type", "") or "") or a.find_parent("sup"):
            a.decompose()
    for sup in body.find_all("sup"):
        sup.decompose()
    blocks = body.find_all(BLOCK_TAGS)
    parts = [b.get_text(" ", strip=True) for b in blocks]
    return "\n\n".join(p for p in parts if p)


def extract(path):
    book = epub.read_epub(path)
    by_id = {it.get_id(): it for it in book.get_items()
             if it.get_type() == ebooklib.ITEM_DOCUMENT}
    chapters, idx = [], 0
    for entry in book.spine:
        item_id = entry[0] if isinstance(entry, (tuple, list)) else entry
        item = by_id.get(item_id)
        if item is None:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        name = item.get_name() or item_id
        kind = _classify(name, _section_type(soup))
        text = _text(soup)
        if not text.strip():
            continue
        chapters.append({
            "index": idx, "id": item_id, "kind": kind,
            "title": _title(soup, name), "text": text,
        })
        idx += 1
    return chapters


def body_chapters(path):
    return [c for c in extract(path) if c["kind"] == "body"]


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/the-time-machine.epub"
    chs = extract(p)
    body = [c for c in chs if c["kind"] == "body"]
    print(f"{os.path.basename(p)}: {len(chs)} spine docs, {len(body)} body chapters\n")
    for c in chs:
        flag = "" if c["kind"] == "body" else f"  [{c['kind']}]"
        print(f"  {c['index']:2d}  {len(c['text']):6d} chars  {c['title'][:46]:46s}{flag}")
    if body:
        print("\n--- first body chapter, first 300 chars ---")
        print(body[0]["text"][:300])
