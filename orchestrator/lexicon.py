#!/usr/bin/env python3
"""Custom pronunciation lexicon: word -> IPA, versioned in git, grows across books.

At render time, each lexicon word in the text is rewritten as a misaki inline override
[word](/ipa/), which Kokoro honors to bypass its own grapheme-to-phoneme guess. This is
the payoff of choosing Kokoro: a confirmed name pronounces correctly everywhere, forever.

Storage is a flat JSON map of lowercased word -> IPA string in lexicon/custom.json.
"""
import json
import os
import re


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save(path, lex):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(lex, f, ensure_ascii=False, indent=2, sort_keys=True)


def add(path, word, ipa):
    lex = load(path)
    lex[word.lower()] = ipa
    save(path, lex)
    return lex


def apply(text, lex):
    """Rewrite each known word as a misaki inline override, preserving display casing."""
    if not lex:
        return text
    # longest words first so multi-part entries win over their substrings
    words = sorted(lex, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)

    def repl(m):
        ipa = lex[m.group(0).lower()]
        return f"[{m.group(0)}](/{ipa}/)"

    return pattern.sub(repl, text)


if __name__ == "__main__":
    demo = {"morlock": "mˈɔɹlɑk", "eloi": "ˈɛloʊaɪ", "weena": "wˈinə"}
    txt = "The Morlocks feared the Eloi, but Weena trusted the Time Traveller."
    print("lexicon:", demo)
    print("IN :", txt)
    print("OUT:", apply(txt, demo))
