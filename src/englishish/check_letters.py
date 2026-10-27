"""Is our letter (1-gram) distribution preserved?  uv run python -m englishish.check_letters

Hugh's check, and it caught two real defects the eye had only vaguely registered:

  1. A SELECTION EFFECT enriching short replacements in rare letters. Rejecting real English
     leaves the residual skewed, because English already took the common-letter strings: at
     length 3, real words carry 12.7% rare-letter mass and the free ones carry 33.6%. Ranking
     could not fix a bucket that had been picked clean. Fixed by refusing to draw below length 5.
  2. OUR OWN AFFIX. `-ox` as the present participle put an x in every participle
     (`venerox`, `irredox`). Affixes dominate letter statistics because they recur on every
     inflected word -- which is why English's own (`-s -es -ed -ing -er -est`) use nothing but
     top-10 letters. Fixed by banning jqxzkvw from the affix inventory.

READ THE RATIOS CAREFULLY. They mislead badly on rare letters: z at 1.5x of English's 0.07% is
an excess of 0.035 percentage points, while w at 0.52x of 2.4% is a deficit of 1.2pp -- 34x
larger, and the one a reader would actually notice.


The claim under test: replacements over-use rare letters (y, z, x, k) relative to real English,
and short replacements are the worst offenders.

Measured token-weighted, because the question is about "large blocks of text" -- each word's
letters count in proportion to how often the word occurs, not once per dictionary entry.

The apples-to-apples comparison is the REPLACED SUBSET: for the words a reader at vocabulary V
does not know, compare the letters of the English originals against the letters of their
English-ish replacements. Anything else confounds "our generator is biased" with "the tail of
English has different letters from the head".
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/Users/hugh/personal/englishish/src")
from wordfreq import word_frequency  # noqa: E402

ALPHA = "abcdefghijklmnopqrstuvwxyz"
d = json.loads(Path(__file__).resolve().parents[2] / "public" / "lexicon.json".read_text())
words = d["words"]


def dist(pairs: list[tuple[str, float]]) -> dict[str, float]:
    """Token-weighted letter distribution."""
    c: Counter[str] = Counter()
    for w, f in pairs:
        for ch in w:
            if ch in ALPHA:
                c[ch] += f
    tot = sum(c.values()) or 1
    return {ch: c[ch] / tot for ch in ALPHA}


# English baseline: every mapped word, weighted by corpus frequency.
eng_all = [(w, word_frequency(w, "en")) for w in words]
eng_dist = dist(eng_all)

print("=== ENGLISH baseline (token-weighted over all mapped words) ===")
top = sorted(eng_dist.items(), key=lambda kv: -kv[1])[:8]
print("  " + "  ".join(f"{ch}={p:.1%}" for ch, p in top))

print("\n=== REPLACED SUBSET: English originals vs English-ish replacements ===")
print("   (words a reader at vocabulary V does not know)\n")
for vocab in (50_000, 10_000, 2_000, 800):
    subset = [(w, v[0], word_frequency(w, "en")) for w, v in words.items() if v[1] >= vocab]
    if not subset:
        continue
    src = dist([(w, f) for w, _i, f in subset])
    ish = dist([(i, f) for _w, i, f in subset])
    # per-letter ratio, ours vs the originals we replaced
    ratios = sorted(
        ((ish[ch] / src[ch] if src[ch] > 1e-12 else float("inf"), ch) for ch in ALPHA),
        reverse=True,
    )
    tokens = sum(f for _w, _i, f in subset)
    total_tokens = sum(f for _w, f in eng_all)
    print(f"  vocab {vocab:>6,}: {len(subset):>6,} lemmas replaced "
          f"= {tokens / total_tokens:.1%} of running text")
    over = [f"{ch}x{r:.1f}" for r, ch in ratios[:6]]
    under = [f"{ch}x{r:.2f}" for r, ch in ratios[-6:]]
    print(f"     MOST over-used: {'  '.join(over)}")
    print(f"     MOST under-used: {'  '.join(under)}")
    # chi-square-ish total divergence
    tv = 0.5 * sum(abs(ish[ch] - src[ch]) for ch in ALPHA)
    print(f"     total variation distance: {tv:.3f}")
    mean_src = sum(len(w) * f for w, _i, f in subset) / tokens
    mean_ish = sum(len(i) * f for _w, i, f in subset) / tokens
    print(f"     mean length: English {mean_src:.2f} -> English-ish {mean_ish:.2f}\n")

print("=== IS THE BIAS LENGTH-DEPENDENT? (replacements grouped by their own length) ===")
print("   ratio of rare-letter mass (j q x z k v w y) ours vs English baseline\n")
RARE = "jqxzkvwy"
eng_rare = sum(eng_dist[ch] for ch in RARE)
for L in range(2, 11):
    sub = [(v[0], word_frequency(w, "en")) for w, v in words.items() if len(v[0]) == L]
    if len(sub) < 30:
        continue
    dl = dist(sub)
    ours_rare = sum(dl[ch] for ch in RARE)
    print(f"  replacement length {L:>2}: {len(sub):>6,} words   "
          f"rare-letter mass {ours_rare:6.1%}  vs English {eng_rare:.1%}   "
          f"= {ours_rare / eng_rare:4.1f}x")

print("\n=== WHY: what does the 3-letter bucket actually have left? ===")
sys.path.insert(0, "/Users/hugh/personal/englishish/src")
from englishish.data import is_real_word  # noqa: E402
from itertools import product  # noqa: E402

three = ["".join(p) for p in product(ALPHA, repeat=3)]
real3 = [w for w in three if is_real_word(w)]
free3 = [w for w in three if not is_real_word(w)]
print(f"  of 17,576 three-letter strings: {len(real3):,} are real English, {len(free3):,} are free")
print(f"  rare-letter mass among the REAL ones: "
      f"{sum(1 for w in real3 for ch in w if ch in RARE) / (3 * len(real3)):.1%}")
print(f"  rare-letter mass among the FREE ones: "
      f"{sum(1 for w in free3 for ch in w if ch in RARE) / (3 * len(free3)):.1%}")
print("\n  English took the common-letter strings. Rejecting real words leaves the residual")
print("  systematically enriched in rare letters -- a selection effect, not a ranking bug.")
