"""Render English text as English-ish at a given vocabulary size, and inspect the lexicon."""

from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path

LEXICON = Path(__file__).resolve().parents[2] / "public" / "lexicon.json"
TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[^A-Za-z]+")


def load() -> dict:
    return json.loads(LEXICON.read_text())


def match_case(src: str, sub: str) -> str:
    if src.isupper() and len(src) > 1:
        return sub.upper()
    if src[0].isupper():
        return sub.capitalize()
    return sub


def render(text: str, words: dict, vocab: int, sharpness: float | None = None,
           seed: int = 7) -> tuple[str, float]:
    """Substitute every word outside the reader's vocabulary. Returns (text, coverage).

    `sharpness` turns the hard top-N threshold into a logistic in log-rank. A real learner's
    knowledge isn't a step function -- it's a smooth curve with idiosyncratic holes and spikes
    (you know `photosynthesis` from school but not `shrug`). The field's own instrument is
    probabilistic (IRT/Rasch), and Laufer called the lexical threshold probabilistic in 1989.
    None = hard cutoff.
    """
    rng = random.Random(seed)
    out: list[str] = []
    known = total = 0

    for tok in TOKEN_RE.findall(text):
        if not tok[0].isalpha():
            out.append(tok)
            continue
        total += 1
        entry = words.get(tok.lower())
        if entry is None:
            out.append(tok)  # OOV: proper nouns, typos. ~2-4% of tokens; Nation counts them separately.
            known += 1
            continue
        sub, rank = entry
        if sharpness is None:
            is_known = rank < vocab
        else:
            # P(know) = sigmoid(a * (log(vocab) - log(rank)))
            x = sharpness * (math.log(vocab + 1) - math.log(rank + 1))
            is_known = rng.random() < 1 / (1 + math.exp(-x))
        if is_known:
            known += 1
            out.append(tok)
        else:
            out.append(match_case(tok, sub))
    return "".join(out), (known / total if total else 1.0)


TEXT = (
    "It is a truth universally acknowledged, that a single man in possession of a good "
    "fortune, must be in want of a wife. However little known the feelings or views of "
    "such a man may be on his first entering a neighbourhood, this truth is so well fixed "
    "in the minds of the surrounding families, that he is considered the rightful property "
    "of some one or other of their daughters."
)


def main() -> None:
    data = load()
    words = data["words"]
    meta = data["meta"]
    print(f"lexicon: {meta['surface_forms']:,} surface forms from {meta['lemmas']:,} lemmas, "
          f"{meta['irregular_lemmas']} irregular")
    print(f"affixes: {meta['affixes']}\n")

    print("=== THE MAP: top 20 English words ===")
    top = sorted(((v[1], k) for k, v in words.items()), key=lambda x: x[0])[:20]
    print("  " + "   ".join(f"{k}→{words[k][0]}" for _, k in top))

    print("\n=== MIRRORED IRREGULARITY (the point of v0) ===")
    families = [
        ("sing", ["sings", "sang", "sung", "singing"]),
        ("break", ["breaks", "broke", "broken", "breaking"]),
        ("know", ["knows", "knew", "known", "knowing"]),
        ("bring", ["brings", "brought", "bringing"]),
        ("keep", ["keeps", "kept", "keeping"]),
        ("find", ["finds", "found", "finding"]),
        ("cut", ["cuts", "cutting"]),
        ("mouse", ["mice"]),
        ("child", ["children"]),
        ("leaf", ["leaves"]),
        ("analysis", ["analyses"]),
        ("cactus", ["cacti"]),
        ("criterion", ["criteria"]),
        ("sheep", []),
    ]
    for lemma, forms in families:
        if lemma not in words:
            print(f"  {lemma:10} MISSING")
            continue
        parts = [f"{lemma}→{words[lemma][0]}"]
        parts += [f"{f}→{words[f][0]}" for f in forms if f in words]
        print(f"  {' | '.join(parts)}")

    print("\n=== REGULAR, for contrast ===")
    for lemma, forms in [("dog", ["dogs"]), ("walk", ["walks", "walked", "walking"])]:
        parts = [f"{lemma}→{words[lemma][0]}"] + [
            f"{f}→{words[f][0]}" for f in forms if f in words
        ]
        print(f"  {' | '.join(parts)}")

    print("\n\n=== THE SLIDER (hard cutoff) ===")
    for vocab in (20_000, 5_000, 2_000, 800, 200, 40):
        body, cov = render(TEXT, words, vocab)
        print(f"\n--- you know the top {vocab:,} lemmas | {cov:.0%} token coverage ---")
        print(f"  {body}")

    print("\n\n=== THE SLIDER (logistic knowledge curve, sharpness=1.6) ===")
    for vocab in (5_000, 800):
        body, cov = render(TEXT, words, vocab, sharpness=1.6)
        print(f"\n--- midpoint {vocab:,} lemmas | {cov:.0%} coverage ---")
        print(f"  {body}")


if __name__ == "__main__":
    main()
