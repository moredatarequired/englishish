"""Witten-Bell interpolated character n-gram.

Hand-rolled deliberately, not as a compromise. kenlm's modified Kneser-Ney *provably*
breaks on a ~30-symbol alphabet: it estimates discounts in closed form from counts of
n-grams seen exactly 1/2/3 times, and with 26 letters there are no singleton unigrams, so
n1=0 and the discount estimate goes negative (kpu/kenlm#290). More data makes it worse.
Witten-Bell's weight is lambda = T/(T+N) -- both direct counts, no discount estimator to
fail. `nltk.lm` has both smoothings but linear-scans every n-gram of the next order on
every score() call (nltk#2495, open since 2020), so it's a test oracle, not a runtime.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict

BOW = "\x02"
EOW = "\x03"
ALPHA = "abcdefghijklmnopqrstuvwxyz"


class CharNGram:
    """Exact sampling and exact log-probability over a closed alphabet.

    Because the alphabet is closed there is no true OOV, so the lowest-order fallback is a
    smoothed uniform and no score can ever be -inf.
    """

    def __init__(self, order: int = 6) -> None:
        self.order = order
        self.support = ALPHA + EOW
        self._ctx: list[dict[str, dict[str, float]]] = [
            defaultdict(lambda: defaultdict(float)) for _ in range(order)
        ]
        self._cache: dict[str, tuple[list[str], list[float]]] = {}

    def train(self, words: list[str]) -> CharNGram:
        """Type-weighted: each word counts once.

        Token-weighting is measurably wrong here -- it makes the model regenerate common
        English (95% real-word collisions vs 21% type-weighted) and flattens the
        length/probability gradient entirely.
        """
        for w in words:
            padded = BOW * (self.order - 1) + w + EOW
            for i in range(self.order - 1, len(padded)):
                sym = padded[i]
                for k in range(self.order):
                    self._ctx[k][padded[i - k : i]][sym] += 1.0
        self._cache.clear()
        return self

    def _dist(self, ctx: str) -> tuple[list[str], list[float]]:
        ctx = ctx[-(self.order - 1) :]
        hit = self._cache.get(ctx)
        if hit is not None:
            return hit
        probs = {c: 1.0 / len(self.support) for c in self.support}
        for k in range(0, len(ctx) + 1):
            table = self._ctx[k].get(ctx[len(ctx) - k :] if k else "")
            if not table:
                continue
            total = sum(table.values())
            if not total:
                continue
            lam = total / (total + len(table))  # Witten-Bell: T/(T+N)
            new = {
                c: lam * (table.get(c, 0.0) / total) + (1 - lam) * probs[c] for c in self.support
            }
            z = sum(new.values())
            probs = {c: p / z for c, p in new.items()}
        out = (list(probs), list(probs.values()))
        self._cache[ctx] = out
        return out

    def logprob(self, word: str) -> float:
        lp = 0.0
        ctx = BOW * (self.order - 1)
        for ch in word + EOW:
            keys, vals = self._dist(ctx)
            lp += math.log(vals[keys.index(ch)])
            ctx = (ctx + ch)[-(self.order - 1) :]
        return lp

    def sample(self, rng: random.Random, max_len: int = 13) -> str | None:
        """Ancestral sampling. Exact -- no MCMC needed, the model is autoregressive."""
        out: list[str] = []
        ctx = BOW * (self.order - 1)
        while len(out) < max_len:
            keys, vals = self._dist(ctx)
            ch = rng.choices(keys, weights=vals)[0]
            if ch == EOW:
                return "".join(out) if out else None
            out.append(ch)
            ctx = (ctx + ch)[-(self.order - 1) :]
        return None  # ran past max_len; reject rather than truncate

    def enumerate_length(self, length: int) -> list[tuple[float, str]]:
        """EVERY string of exactly `length` chars, scored exactly, best-first.

        Necessary rather than merely nice at the short end. A beam of width 4000 at length 4
        yields ~128 usable candidates, because ~97% of the top-by-logprob strings are real
        English words -- the high-probability region is saturated, so pruning it evicts almost
        everything the beam looked at. Enumerating all 456,976 gives ~430k free candidates
        instead. DFS reuses prefix work, so this is cheap up to length 4-5.
        """
        out: list[tuple[float, str]] = []

        def rec(ctx: str, seq: str, lp: float) -> None:
            if len(seq) == length:
                keys, vals = self._dist(ctx)
                out.append((lp + math.log(vals[keys.index(EOW)]), seq))
                return
            keys, vals = self._dist(ctx)
            for c in ALPHA:
                rec((ctx + c)[-(self.order - 1) :], seq + c, lp + math.log(vals[keys.index(c)]))

        rec(BOW * (self.order - 1), "", 0.0)
        out.sort(reverse=True)
        return out

    def beam(self, length: int, width: int = 3000) -> list[tuple[float, str]]:
        """Top-`width` strings of exactly `length` chars, best-first.

        Needed because ancestral sampling almost never visits the short end: the model puts
        its short-string mass on real words, so sampling yields ~136 length-4 candidates in
        140k draws while the space actually holds ~430k non-words.
        """
        beam: list[tuple[float, str]] = [(0.0, "")]
        for _ in range(length):
            nxt: list[tuple[float, str]] = []
            for lp, s in beam:
                keys, vals = self._dist(BOW * (self.order - 1) + s)
                for c in ALPHA:
                    nxt.append((lp + math.log(vals[keys.index(c)]), s + c))
            nxt.sort(reverse=True)
            beam = nxt[: width * 3]
        out = []
        for lp, s in beam:
            keys, vals = self._dist(BOW * (self.order - 1) + s)
            out.append((lp + math.log(vals[keys.index(EOW)]), s))
        out.sort(reverse=True)
        return out[:width]
