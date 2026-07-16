"""Candidate filters.

Three separate mechanisms for three separate problems, which is the whole point:

  * "already English"        -> real_words() membership
  * "already another language" -> foreign_words() membership
  * "emits a slur"           -> blocklist, recall-biased
  * "reads as a typo of the word it replaces" -> distance from the SOURCE

That last one is the subtle one. "Far from EVERY English word" is unsatisfiable: 100% of
length<=4 non-words sit within edit distance 1 of a real word and 96.7% at length 5. But
"far from its own source" is cheap and is what actually
prevents the map feeling like a spelling error. This is the documented English Lexicon Project
failure -- its pseudowords were edit-distance-1 from their base words, so `addomen` is
recoverable from `abdomen` and reaction times got contaminated by base-word frequency. It's
also why Wuggy is wrong for this project by default: it derives each pseudoword from a
specific real word by changing one subsyllabic slot.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache

from rapidfuzz.distance import Levenshtein  # MIT. `import Levenshtein` is GPL-2.0+.
from wordfreq import top_n_list, zipf_frequency

from .data import FOREIGN_LANGS, blocklist, corpus_words, curated_words, is_real_word, training_lexicon

VOWELS = "aeiouy"

# An onset/coda counts as English only if enough REASONABLY COMMON words use it.
MIN_ATTESTATIONS = 6
ATTEST_ZIPF = 2.5


def _onset_end(w: str) -> int:
    """Index where the first vowel nucleus starts.

    Two English orthographic facts a naive vowel scan gets wrong, and both showed up in the
    output as junk words:

      * `qu` is a digraph for /kw/, not q + nucleus u. Scanning naively, `queen`/`quick`/`quite`
        hand bare `q` hundreds of attestations, which legalises `qir`, `qab`, `qoo`.
      * word-initial `y` is the consonant /j/ (`yes`, `you`), not a vowel. Treating it as a
        nucleus makes `ycy` look like a well-formed V-C-V word.
    """
    i = 0
    if w[:1] == "y":  # initial y is /j/, a consonant
        i = 1
    while i < len(w):
        if w[i] == "q" and w[i + 1 : i + 2] == "u":
            i += 2  # `qu` is one onset consonant
            continue
        if w[i] in VOWELS:
            break
        i += 1
    return i


@cache
def legal_clusters() -> tuple[frozenset[str], frozenset[str]]:
    """(onsets, codas) English actually USES, derived from the training lexicon by count.

    Spike 4's real lesson: phonology buys PRONOUNCEABILITY (it does not buy coherence -- that's
    morphology). This is a silent-reading toy so we work orthographically, approximating it by
    requiring consonant clusters English actually uses. That's what separates `ccy`/`vhe`/`mze`
    from `sque`/`prer`/`flomb`, and no amount of n-gram probability does it: a 6-gram happily
    emits `vh` because it never sees a whole word.

    ---------------------------------------------------------------------------------------
    EXISTENCE PROVES NOTHING. This same mistake has now bitten three times in three costumes,
    so it's worth stating once, plainly: any categorical "is X attested?" test against a large
    permissive English word list comes back TRUE almost always, because English's tail is vast
    and junky. The fix is always the same -- require *frequency-weighted* evidence.

      1. The derivational stripper (spike 5) asked "is the remainder a word?" against web2's
         235k entries and produced `international = tern + -ational + in-` (tern, the seabird),
         `between = twee + be- + -en`, `president = side + -ent + pre-`.
      2. This function asked "is this cluster attested?" and one word -- `mzee` -- legalised the
         `mz-` onset, `dziggetai` legalised `dz-`, and the abbreviation `hdqrs` legalised `hd-`.
         So `it -> mze`, `i -> dzu`, `dog -> hdy`.
      3. Raising it to a plain type count didn't fix it either: bare `q` had exactly 14
         attestations, over the threshold -- all Arabic/Chinese loanwords, and *inflated by
         inflection* (`qadi/qadis`, `qibla/qiblah/qiblas` are two lemmas, not five words). So
         `in -> qir`, `i -> qab`.

    Hence: count only attesting words above a frequency floor. `gh-` survives on
    ghost/ghetto/ghastly; bare `q-` does not survive on qadi/qibla/qindarka.
    ---------------------------------------------------------------------------------------
    """
    on_counts: Counter[str] = Counter()
    co_counts: Counter[str] = Counter()
    for w in training_lexicon():
        if zipf_frequency(w, "en") < ATTEST_ZIPF:
            continue
        on_counts[w[: _onset_end(w)]] += 1
        j = len(w)
        while j > 0 and w[j - 1] not in VOWELS:
            j -= 1
        co_counts[w[j:]] += 1
    onsets = {c for c, n in on_counts.items() if n >= MIN_ATTESTATIONS} | {""}
    codas = {c for c, n in co_counts.items() if n >= MIN_ATTESTATIONS} | {""}
    return frozenset(onsets), frozenset(codas)


def pronounceable(w: str) -> bool:
    """Cheap syllable-shape check: legal onset, legal coda, at least one nucleus.

    Interior clusters are left unchecked -- doing it properly needs syllabification, and the
    onset/coda pair catches the overwhelming majority of the junk.
    """
    onsets, codas = legal_clusters()
    if all(c in VOWELS for c in w):
        return False  # all-vowel strings like `uiy` pass onset/coda vacuously
    i = _onset_end(w)
    if i >= len(w):
        return False  # no nucleus at all
    if w[:i] not in onsets:
        return False
    j = len(w)
    while j > 0 and w[j - 1] not in VOWELS:
        j -= 1
    return w[j:] in codas


FOREIGN_ZIPF = 3.0
# An English reader cannot identify a 2-3 letter string as belonging to another language.
FOREIGN_MIN_LEN = 4


@cache
def foreign_words() -> frozenset[str]:
    """Words English readers might recognise as belonging to another language.

    ---------------------------------------------------------------------------------------
    THE FREQUENCY FLOOR IS LOAD-BEARING, and leaving it out was the same bug a third time.

    `top_n_list(lang, N)` is a CORPUS list: it contains every string that appears in that
    language's text, so 2-letter strings are "words" in all of them. Measured, unfloored, this
    filter reported `eb` as a word in French, German, Spanish, Italian, Dutch, Portuguese,
    Swedish, Polish AND Turkish -- nine languages -- and on that basis killed all 33 otherwise-
    free 2-letter candidates, which is where "there are zero free 2-letter strings" actually
    came from. It wasn't English that had claimed the space; it was corpus noise in 41 other
    languages.

    A floor separates the real thing from the noise exactly as intended: `je` is French for "I"
    (zipf ~6, correctly blocked), `eb` is French OCR/abbreviation debris (zipf ~1.5, correctly
    freed). Cost: ~2M zipf lookups once at startup.
    ---------------------------------------------------------------------------------------
    """
    out: set[str] = set()
    for lang in FOREIGN_LANGS:
        try:
            candidates = top_n_list(lang, 50_000)
        except LookupError:
            continue
        for w in candidates:
            if not (w.isascii() and w.isalpha()):
                continue
            try:
                if zipf_frequency(w, lang) >= FOREIGN_ZIPF:
                    out.add(w)
            except (LookupError, ModuleNotFoundError):
                break  # language needs a tokenizer we don't have; skip it entirely
    return frozenset(out)


class Filters:
    def __init__(self) -> None:
        self.curated = curated_words()
        self.corpus = corpus_words()
        self.foreign = foreign_words()
        self.sub_pats, self.exact_pats = blocklist()
        self._sub_re = re.compile("|".join(sorted(map(re.escape, self.sub_pats), key=len, reverse=True)))

    def is_real(self, w: str) -> bool:
        """Dictionaries always; the corpus list only above the length where it's informative."""
        return is_real_word(w)

    def is_foreign(self, w: str) -> bool:
        """Would an English reader recognise this as another language's word?

        NOT "is this a word in language L?" -- that's a different question, and answering it
        instead is what emptied the 2-letter space. `eb` is genuinely Dutch (it means "ebb", zipf
        3.48), `ek`/`ig`/`ub` likewise, so a correct Dutch-wordhood oracle correctly kills them --
        and kills the whole 2-letter pool with them. But no English reader clocks `eb` as Dutch.
        The filter exists to avoid emitting `hola`/`merci`/`danke`, which are recognisable; below
        4 characters nothing is, so consulting it there costs everything and buys nothing.

        Match the oracle to the question you're actually asking.
        """
        return len(w) >= FOREIGN_MIN_LEN and w in self.foreign

    def is_profane(self, w: str) -> bool:
        return w in self.exact_pats or bool(self._sub_re.search(w))

    def too_close(self, cand: str, source: str) -> bool:
        """Reject candidates recoverable from the word they replace.

        Threshold scales with length: short words have little room, so demanding a large
        distance from a 3-letter source is unsatisfiable.
        """
        need = 2 if len(source) <= 4 else 3
        return Levenshtein.distance(cand, source, score_cutoff=need) < need

    def acceptable(self, w: str) -> bool:
        """Source-independent checks.

        At >=7 characters the real-word and foreign checks are nearly moot (0.2% and 0.08% hit
        rates) but they're set lookups, so there's no reason to skip them.
        """
        return pronounceable(w) and not (
            self.is_real(w) or self.is_foreign(w) or self.is_profane(w)
        )
