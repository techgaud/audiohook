#!/usr/bin/env python3
"""Light, conservative text normalization for TTS.

The goal is fewer mispronunciations and fewer false sentence splits, without
rewriting the author. Heavy-handed normalization causes more harm than good, so
this only fixes encoding, unifies punctuation, expands a small safe set of
abbreviations, and tidies whitespace.
"""
import re

import ftfy

# Safe expansions. Ambiguous ones (St. = Saint or Street, No. = Number or no) are
# deliberately left alone.
ABBREV = [
    (r"\bMrs\.", "Missus"), (r"\bMr\.", "Mister"), (r"\bMs\.", "Miss"),
    (r"\bDr\.", "Doctor"), (r"\bProf\.", "Professor"), (r"\bRev\.", "Reverend"),
    (r"\bSt\.(?=\s+[A-Z][a-z])", "Saint"),          # St. John, not Main St.
    (r"\betc\.", "et cetera"), (r"\bvs\.", "versus"), (r"\be\.g\.", "for example"),
    (r"\bi\.e\.", "that is"),
]
_ABBREV = [(re.compile(p), r) for p, r in ABBREV]


def normalize(text):
    text = ftfy.fix_text(text)
    # unify dashes and ellipsis to speakable punctuation
    text = text.replace("—", ", ").replace("–", "-")   # em dash to comma-pause, en dash to hyphen
    text = text.replace("…", "...")
    # straighten quotes (misaki and Kokoro handle straight quotes most reliably)
    text = (text.replace("“", '"').replace("”", '"')
                .replace("‘", "'").replace("’", "'"))
    for pat, repl in _ABBREV:
        text = pat.sub(repl, text)
    # collapse runs of spaces, keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


if __name__ == "__main__":
    sample = ('“Mr. Wells,” he said—slowly—“the Morlocks… '
              'they live underground.”  Dr. Smith   agreed.')
    print("IN :", sample)
    print("OUT:", normalize(sample))
