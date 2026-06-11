#!/usr/bin/env python3
"""Find pronunciation-risk words for the human-in-the-loop review step.

What espeak (Kokoro's fallback) actually mispronounces is NAMES and genuinely RARE or
invented words, not every word missing from misaki's curated dictionary (that dictionary
omits many common inflected words like "opened" or "towards" that espeak handles fine, so
using misaki-unknown alone floods the reviewer). So a word is a review candidate when:
  - misaki does not already have a correct pronunciation for it (the gate), AND
  - it is either a named entity (spaCy NER) or rare in general English (low wordfreq).
Candidates are ranked names-first then by frequency, so the few names that recur across a
whole book rise to the top. The reviewer supplies IPA, which lands in lexicon/custom.json
and is injected as a misaki inline override at render time. See lexicon.py.
"""
import re
import sys
from collections import Counter, defaultdict

NAMEY = {"PERSON", "GPE", "LOC", "FAC", "ORG", "NORP", "PRODUCT", "EVENT",
         "WORK_OF_ART", "LANGUAGE"}
_ROMAN = re.compile(r"^[IVXLCDM]+$")

_lex = None
_nlp = None


def _load():
    global _lex, _nlp
    if _lex is None:
        from misaki import en
        _lex = en.G2P(trf=False, british=False).lexicon
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
    return _lex, _nlp


def is_known(word, lex, tag=None):
    """True if misaki already has a correct pronunciation (dictionary or morphology)."""
    if any(v in lex.golds or v in lex.silvers
           for v in (word, word.lower(), word.capitalize(), word.upper())):
        return True
    if tag:
        try:
            if lex.is_known(word, tag):
                return True
        except Exception:
            pass
    return False


def scan(chapters, rare_zipf_threshold=2.5, min_count=1):
    from wordfreq import zipf_frequency
    lex, nlp = _load()

    counts = Counter()
    case_votes = defaultdict(Counter)
    labels = {}             # lower -> NER label (spaCy splits possessives, so no "Weena's")

    for ch in chapters:
        for tok in nlp(ch["text"]):
            t = tok.text
            if not t.isalpha() or len(t) < 2:
                continue
            if _ROMAN.match(t.upper()) and t.isupper():
                continue
            if is_known(t, lex, tok.tag_):
                continue
            low = t.lower()
            counts[low] += 1
            case_votes[low][t] += 1
            if tok.ent_type_ in NAMEY and low not in labels:
                labels[low] = tok.ent_type_

    rows = []
    for low, n in counts.items():
        if n < min_count:
            continue
        z = round(zipf_frequency(low, "en"), 2)
        label = labels.get(low)
        # espeak gets names and rare words wrong; skip common non-names it handles fine
        if not (label or z < rare_zipf_threshold):
            continue
        word = case_votes[low].most_common(1)[0][0]
        rows.append({
            "word": word, "count": n, "label": label or "rare",
            "zipf": z, "ipa": None,       # ipa filled by the reviewer
        })
    # names first, then by frequency, then rarer first
    rows.sort(key=lambda r: (r["label"] == "rare", -r["count"], r["zipf"], r["word"].lower()))
    return rows


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from orchestrator import epub_to_chapters, text_normalize
    p = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/the-time-machine.epub"
    chs = epub_to_chapters.body_chapters(p)
    for c in chs:
        c["text"] = text_normalize.normalize(c["text"])
    rows = scan(chs, min_count=1)
    print(f"{len(rows)} review candidates (words misaki does not know)\n")
    print(f"  {'word':18s} {'count':>5}  {'label':12s} zipf")
    for r in rows[:30]:
        print(f"  {r['word']:18s} {r['count']:>5}  {r['label']:12s} {r['zipf']}")
