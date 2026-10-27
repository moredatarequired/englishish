"""Generate English-ish's non-finite verb forms and show them mirrored through the ablaut classes.

    uv run python -m englishish.demo_nonfinite
"""

from __future__ import annotations

from rapidfuzz.distance import Levenshtein

from . import morphology as M
from . import nonfinite as NF
from .build import ENGLISH_AFFIXES, pick_affixes
from .data import training_lexicon
from .filters import Filters
from .ngram import CharNGram

# The English periphrases these replace, so we don't generate an affix that collides with the
# words it's meant to absorb.
EXTRA_BLOCK = set("for to while having about vain nothing almost tried".split())


def pick_nonfinite_affixes(model: CharNGram, filters: Filters, taken: set[str]) -> dict[str, str]:
    """Affixes for the new forms, from the same generator, mutually distinct from everything.

    Non-finite affixes run longer than the inflectional ones on purpose: these are younger,
    freshly grammaticalized from full words, and a newer affix is phonologically bulkier because
    erosion hasn't had time to work on it yet. `-gonna` is longer than `-s`. Real languages
    stratify by age this way, so English-ish should too.

    THESE NEED THE REAL-WORD FILTER, unlike the 2-3 char inflectional affixes. The rule "a bound
    morpheme never stands alone, so it needn't avoid being a word" holds at length 2-3, where
    essentially nothing is a word. At length 4-5 it collapses: the model's top strings are
    overwhelmingly real English, and the first run handed back `-king -fish -work -head -back`.
    `gnud` + `-king` reads as "gnud king" -- a compound with an English noun, which leaks English
    straight back into English-ish. Length decides whether the filter is needed, not boundness.

    (Real affixes *are* often homophonous with words -- `-ful`~full, `-like`~like, `-hood`,
    `-ship` -- precisely because they grammaticalized from them. But the source word should be an
    ENGLISH-ISH word, not an English one. Doing that properly means eroding an actual English-ish
    content word, which is the right v1 move and is noted in the module docstring.)
    """
    reserved = set(M.reserved_affixes()) | ENGLISH_AFFIXES | EXTRA_BLOCK | taken
    supply: list[str] = []
    for length in (4, 5):
        for _, cand in model.beam(length, 3000):
            if cand in reserved or not filters.acceptable(cand):
                continue
            if any(Levenshtein.distance(cand, p, score_cutoff=3) < 3
                   for p in [*supply, *taken]):
                continue
            supply.append(cand)
    it = iter(supply)
    return {slot: next(it) for slot in NF.NONFINITE}


def main() -> None:
    print("training generator (SCOWL 70, type-weighted, order 6)...\n")
    model = CharNGram(6).train(list(training_lexicon()))

    filters = Filters()
    affixes = pick_affixes(model)
    taken = set(affixes.values())
    nf = pick_nonfinite_affixes(model, filters, taken)

    print("=" * 84)
    print("NEW NON-FINITE FORMS -- categories English lacks")
    print("=" * 84)
    for slot, (base, gloss, eng, src) in NF.NONFINITE.items():
        print(f"\n  -{nf[slot]:<8}  {gloss.upper()}")
        print(f"     built on the {base.lower()} stem")
        print(f"     English needs:   \"{eng}\"")
        print(f"     grammaticalized from: {src}")

    print("\n" + "=" * 84)
    print("EXISTING inflectional affixes, for contrast (older = shorter, as erosion predicts)")
    print("=" * 84)
    print("  " + "   ".join(f"{k}=-{v}" for k, v in affixes.items()))

    # Stems chosen to span the classes, using the shapes the real build produced.
    cases = [
        ("sing", "gned", "ablaut_i_a_u (sing/sang/sung)"),
        ("break", "gette", "ablaut_ea_o_o (break/broke/broken)"),
        ("keep", "trii", "ept (keep/kept)"),
        ("bring", "yalve", "ought (bring/brought)"),
        ("cut", "spirn", "zero_pst (cut/cut/cut)"),
        ("walk", "sely", "REGULAR"),
        ("dance", "clurn", "REGULAR"),
    ]

    print("\n" + "=" * 84)
    print("MIRRORED THROUGH THE ABLAUT CLASSES")
    print("Irregularity propagates into the new forms wherever they're built on a past stem --")
    print("exactly why Latin verbs have principal parts.")
    print("=" * 84)

    for lemma, stem, cls in cases:
        print(f"\n  {lemma}  ->  {stem}      [{cls}]")
        pst = M.realize(stem, lemma, M.PST, affixes)
        ptcp = M.realize(stem, lemma, M.PTCP_PST, affixes)
        print(f"     bases:  present={stem}   past={pst}   participle={ptcp}")
        forms = NF.paradigm(stem, lemma, affixes, nf)
        for slot, (base, gloss, eng, _s) in NF.NONFINITE.items():
            if slot not in forms:
                continue
            irreg = M.class_of(lemma) is not None
            tag = "  <- inherits ablaut" if base != NF.PRESENT and irreg and pst != stem else ""
            print(f"     {slot:<12} {forms[slot]:<18} \"{eng}\"{tag}")

    print("\n" + "=" * 84)
    print("WHAT THIS BREAKS")
    print("=" * 84)
    print("""
  lexicon.json maps english_wordform -> englishish_wordform. These forms have no English
  wordform to key on -- English needs a whole construction. So:

    "in order to sing"        ->  1 word   (supine)
    "while singing"           ->  1 word   (simultaneous converb)
    "having sung, he left"    ->  1 word + he left
    "tried to sing and failed"->  1 word   (frustrative)

  Going English -> English-ish stops being substitution and becomes translation: you have to
  recognise the construction and collapse it. Adding a category English lacks breaks the
  word-for-word bijection in the direction nobody was watching.
""")


if __name__ == "__main__":
    main()
