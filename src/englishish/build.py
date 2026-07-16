"""Build lexicon.json -- the whole artifact boundary.

Everything upstream of this file can be replaced (surface char n-gram -> joint
grapheme-phoneme model -> evolved-by-sound-change lexicon) without the frontend knowing.
That's the point: ship v0 now, improve the generator forever.

Pipeline:
  1. train a type-weighted char n-gram on SCOWL 70 (modern, curated, no proper nouns)
  2. build the ENGLISH LEMMA inventory, ranked by summed-form frequency
  3. generate an English-ish stem pool -- beam the short end, sample the long end
  4. filter: not real, not foreign, not profane, not a typo of its own source
  5. assign length-stratified, monotone within each length bucket
  6. realize every inflected form, mirroring English's irregular classes
  7. emit a flat surface map: english_wordform -> [englishish_wordform, lemma_rank]

Ranking by LEMMA rather than wordform is the load-bearing choice. It's what makes "if you
know `mouse` you know `mice`" true, and it resolves the unit confusion that makes type-ranked
coverage numbers incomparable to the lexical-coverage literature (which counts families).
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein
from wordfreq import word_frequency, zipf_frequency

from . import morphology as M
from .data import training_lexicon, unimorph
from .filters import Filters
from .ngram import CharNGram

SEED = 0xE4611
MAX_LEMMAS = 50_000
ENUM_LENGTHS = (2, 3, 4)        # exhaustive: the short end is saturated by real English
BEAM_LENGTHS = (5, 6)           # beam: 26^5 is 11.8M, too many to enumerate
BEAM_WIDTH = 60_000
LONG_TARGET = 90_000            # candidates at length >= 7, which only sampling reaches
KEEP_PER_LENGTH = 30_000        # trim: length 4 enumerates to ~425k and we need far fewer
MAX_TRIES = 60                  # candidates to try per (lemma, length) before widening
OUT = Path(__file__).resolve().parents[2] / "public" / "lexicon.json"


def build_lemma_index() -> tuple[list[tuple[str, float]], dict[str, dict[str, str]]]:
    """(ranked [(lemma, zipf)], lemma -> {slot: english_surface_form}).

    Lemma frequency is the SUM over its surface forms -- that's the aggregation that makes a
    lemma-ranked slider mean "you know this word and its inflections".
    """
    um = unimorph()
    forms: dict[str, dict[str, str]] = defaultdict(dict)
    freq: dict[str, float] = defaultdict(float)

    for lemma, rows in um.items():
        if not lemma.isalpha() or len(lemma) < 2:
            continue
        total = word_frequency(lemma, "en")
        for form, feats in rows:
            slot = M.UNIMORPH_SLOTS.get(feats)
            if slot is None or not form.isalpha():
                continue
            # UniMorph carries Wiktionary parse errors (go -> "countable"/N;PL). A form that
            # shares no prefix with its lemma and isn't a known irregular is almost always junk.
            if not form.startswith(lemma[:2]) and M.class_of(lemma) is None:
                continue
            forms[lemma][slot] = form
            total += word_frequency(form, "en")
        freq[lemma] = total

    # Lemmas absent from UniMorph (incl. `be`, and every function word) still need entries.
    from wordfreq import top_n_list

    for w in top_n_list("en", 120_000):
        if w.isalpha() and len(w) >= 1 and w not in freq:
            freq[w] = word_frequency(w, "en")

    ranked = sorted(freq.items(), key=lambda kv: -kv[1])
    ranked = [(w, zipf_frequency(w, "en")) for w, f in ranked if f > 0][:MAX_LEMMAS]
    return ranked, {k: dict(v) for k, v in forms.items()}


NATURALNESS_MARGIN = 0.30  # nats/char below a real English word of the same length
# Hard floor on replacement length. Starving the short buckets isn't enough: the naturalness floor
# leaves 9 candidates at length 3 and 28 at length 4, and the 9 most frequent English words then
# consume all 9 -- so `the`/`of`/`i`/`is` still drew from the one bucket whose letters are wrong
# (11.1% and 8.9% rare-letter mass, vs English's 6.5%). Below 5 characters there is nothing left
# worth having, so don't look.
MIN_STEM_LEN = 5


def naturalness_floors(model: CharNGram, lex: list[str]) -> dict[int, float]:
    """Per-length floor: how English-like must a candidate of length L be?

    Measured against real English words OF THE SAME LENGTH, because per-character logprob is
    strongly length-dependent -- real English's median runs -3.92 at length 2, -2.94 at 3, -1.99
    at 5, -1.17 at 11. Deeper into a word the n-gram context is richer and the continuation is
    more predictable, so an absolute floor is meaningless: it would reject real 3-letter English
    words as insufficiently English.
    """
    out: dict[int, float] = {}
    by_len: dict[int, list[str]] = defaultdict(list)
    for w in lex:
        by_len[len(w)].append(w)
    for length, words in by_len.items():
        if len(words) < 50:
            continue
        vals = sorted(model.logprob(w) / (len(w) + 1) for w in words[:1200])
        out[length] = vals[len(vals) // 2] - NATURALNESS_MARGIN
    return out


def build_stem_pool(model: CharNGram, filters: Filters) -> dict[int, list[str]]:
    """length -> candidates that clear the naturalness floor, best-first by logprob.

    ---------------------------------------------------------------------------------------
    THE FLOOR IS WHAT FIXES SHORT WORDS, and the reason is a selection effect, not a ranking bug.

    Rejecting real English words leaves a residual systematically enriched in RARE LETTERS,
    because English already took the common-letter strings. Measured at length 3: of 17,576
    strings, 2,386 are real English with 12.7% rare-letter mass (jqxzkvwy); the 15,190 free ones
    carry 33.6% -- a 2.6x enrichment. Ranking by logprob pulls our selected length-3 words back
    down to 10.6%, which is real work, but it cannot reach English's 6.5%, because the good
    strings are simply gone. No amount of re-ranking WITHIN a bucket fixes a bucket that's been
    picked clean.

    So the fix is to stop drawing from those buckets. An absolute per-length floor starves length
    3 to ~9 candidates and length 4 to ~28, and assignment falls through to length 5+, where
    rare-letter mass is 5.0-5.7% -- at or BELOW English's own.

    The cost is longer words, and it's worth paying: Zipf's law of abbreviation is rho ~= 0.12
    (1.5% of variance in word length) and it SATURATES past the common core, so per-word length
    matching buys almost nothing in realism. We were enforcing a worthless constraint at the
    price of the one thing a reader can actually see.

    (Ranking by logprob is still the wrong objective -- it explains only ~16-30% of human
    wordlikeness, and neighborhood density beats it in our regime (Bailey & Hahn 2001). It's also
    mildly circular: scoring candidates with the model that generated them. Swapping the key
    touches only this function.)
    ---------------------------------------------------------------------------------------
    """
    rng = random.Random(SEED)
    pool: dict[int, set[str]] = defaultdict(set)

    # ENUMERATE the short end. Ancestral sampling essentially never visits it (the model puts
    # its short-string mass on real words), and a beam doesn't rescue it either: ~97% of the
    # top-by-logprob short strings ARE real English, so a width-4000 beam at length 4 yields
    # ~128 usable candidates out of ~430k that actually exist. (An earlier version of this comment
    # claimed there are ZERO free 2-letter strings and that short function words therefore must get
    # longer counterparts. That was an oracle bug, not a fact -- see data.is_real_word(). There are
    # 33.)
    for length in ENUM_LENGTHS:
        for _, cand in model.enumerate_length(length):
            if filters.acceptable(cand):
                pool[length].add(cand)
    for length in BEAM_LENGTHS:
        for _, cand in model.beam(length, BEAM_WIDTH):
            if filters.acceptable(cand):
                pool[length].add(cand)

    # Sample the long end. The target counts ONLY length>=7, because the enumeration above
    # already returns ~500k short candidates -- gating on the total would exit immediately and
    # leave the entire long tail unmapped.
    seen: set[str] = set()
    tries = 0
    while sum(len(v) for L, v in pool.items() if L >= 7) < LONG_TARGET and tries < 900_000:
        tries += 1
        w = model.sample(rng, max_len=18)  # long enough for the tail of the lemma list
        if not w or len(w) < 2 or w in seen:
            continue
        seen.add(w)
        if filters.acceptable(w):
            pool[len(w)].add(w)

    floors = naturalness_floors(model, list(training_lexicon()))
    out: dict[int, list[str]] = {}
    for L, ws in pool.items():
        if L < MIN_STEM_LEN:
            continue
        floor = floors.get(L)
        keep = ws if floor is None else {w for w in ws if model.logprob(w) / (L + 1) >= floor}
        if keep:
            out[L] = sorted(keep, key=model.logprob, reverse=True)[:KEEP_PER_LENGTH]
    return out


# Slots grouped by the paradigm they belong to. Signatures are compared WITHIN a group, never
# across, because English collides `N;PL` with `V;PRS;3;SG` for every noun-verb homograph --
# `walk` -> `walks` twice -- and that's an accident of English spelling both with -s, not a fact
# about the paradigms. English-ish uses distinct plural and 3SG affixes, so it never collides
# them; demanding it inherit the collision rejects `walk`, `run`, `look`, `work` and most of the
# language. (This is the same "should English-ish inherit English's homographs?" question, and
# the answer here is no: it's orthographic coincidence, not structure.)
SLOT_GROUPS = (
    ("LEMMA", M.PL),
    ("LEMMA", M.TSG, M.PST, M.PTCP_PST, M.PTCP_PRS),
    ("LEMMA", M.CMPR, M.SPRL),
)


def signature(paradigm: dict[str, str], group: tuple[str, ...]) -> frozenset[frozenset[str]]:
    """Which slots of `group` share a surface form. Partitions the sub-paradigm by realization."""
    groups: dict[str, set[str]] = defaultdict(set)
    for slot in group:
        form = paradigm.get(slot)
        if form is not None:
            groups[form].add(slot)
    return frozenset(frozenset(v) for v in groups.values())


def realize_paradigm(
    stem: str,
    lemma: str,
    eng_forms: dict[str, str],
    affixes: dict[str, str],
    spare: list[str],
    spare_pos: int,
    filters: Filters,
) -> dict[str, str] | None:
    """The full English-ish paradigm, or None if it's unusable.

    Rejects on two counts: an inflected form that trips the blocklist, or a paradigm that isn't
    isomorphic to English's.

    THE BLOCKLIST MUST RUN ON COMPOSED FORMS, not just on stems. Filtering the generator's
    output is not enough, because affixation manufactures new strings. Measured on the first
    clean build: 52 leaks, every one composed rather than generated --
    `apped` + PTCP_PRS `-ox` -> `appedox` contains "pedo"; `luxurian` + 3SG `-us` -> `luxurianus`
    contains "anus", and so did `oliganus`, `extranus`, `amianus`, `diamanus`. Every stem
    involved was clean. The affix did it.

    The constraint is faithfulness, not mere distinctness: **English-ish forms must collide
    exactly where English's forms collide.** `walk/walked/walked` collapses past and
    participle, so English-ish must too; `sing/sang/sung` distinguishes all three, so English-ish
    must too; `cut/cut/cut` collapses everything, so English-ish must too. Requiring all forms
    to be distinct would be wrong -- it would over-differentiate exactly the regular paradigms.

    This catches a whole class of silent failures. `sing -> ught` looks fine until you realize
    the stem opens with its own vowel, so the i->a->u ablaut is a no-op and `sung` comes out
    `ught` as well: the distinction just evaporates. Comparing signatures rejects that stem and
    the assignment moves on.
    """
    eng = {"LEMMA": lemma, **eng_forms}
    ish: dict[str, str] = {"LEMMA": stem}
    used = 0
    for slot in eng_forms:
        got = M.realize(stem, lemma, slot, affixes)
        if got is None:  # suppletive: an unrelated stem, exactly as go/went
            if spare_pos + used >= len(spare):
                return None
            got = spare[spare_pos + used]
            used += 1
        if filters.is_profane(got):
            return None
        ish[slot] = got
    for group in SLOT_GROUPS:
        if signature(eng, group) != signature(ish, group):
            return None
    out = {k: v for k, v in ish.items() if k != "LEMMA"}
    out["__spare_used__"] = used
    return out


def assign(
    ranked: list[tuple[str, float]],
    forms: dict[str, dict[str, str]],
    pool: dict[int, list[str]],
    filters: Filters,
    affixes: dict[str, str],
    spare: list[str],
) -> tuple[dict[str, dict[str, str]], int, int]:
    """Length-stratified, monotone-within-stratum assignment, validated per paradigm.

    Global monotonicity by raw logprob does NOT work: it maps `the` -> `disting`, because the
    high-probability short region really is dominated by real English and pruning it evicts most
    short candidates. Stratifying by length and holding monotonicity within each bucket is a
    refinement rather than a compromise -- length is part of what makes a frequent word
    plausible, so this serves the goal (English-ish self-consistent as a language) better.

    Zipf's law of abbreviation is weak (rho ~= 0.12) and SATURATES past the common core, so
    the length gradient only matters in the top few thousand ranks; length-matching per word
    handles it without fitting a curve.

    Assignment and realization are fused because a stem can only be judged by the paradigm it
    produces -- a stem that collapses `sing`/`sung` has to be rejected and the next one tried.
    """
    cursor: dict[int, int] = defaultdict(int)
    out: dict[str, dict[str, str]] = {}
    starved = 0
    rejected = 0
    spare_pos = 0

    for lemma, _zipf in ranked:
        L = len(lemma)
        eng_forms = forms.get(lemma, {})
        # Nearest available lengths first. Must be dynamic, not a fixed offset tuple: the
        # naturalness floor empties lengths 2-4, and from L=1 a (L..L+3) window would top out at
        # 4 and starve. Preferring closer lengths keeps the (weak) length gradient where it's
        # satisfiable and abandons it where it isn't.
        for cand_len in sorted(pool, key=lambda cl: (abs(cl - L), cl))[:8]:
            bucket = pool.get(cand_len)
            if not bucket:
                continue
            i = cursor[cand_len]
            chosen = None
            # Bounded scan. Unbounded, this is quadratic: a rejected candidate doesn't advance the
            # cursor (it may suit a later lemma), so every subsequent lemma re-scans and re-rejects
            # the same accumulated garbage -- 15M rejections per build, and adding the composed-form
            # profanity check pushed it past 7 minutes. We're choosing among ~30k near-equivalent
            # candidates, so trying more than a few dozen buys nothing.
            stop = min(len(bucket), i + MAX_TRIES)
            while i < stop:
                cand = bucket[i]
                if filters.too_close(cand, lemma):
                    i += 1
                    continue
                para = realize_paradigm(
                    cand, lemma, eng_forms, affixes, spare, spare_pos, filters
                )
                if para is None:
                    rejected += 1
                    i += 1
                    continue
                chosen = (cand, para)
                break
            if chosen is not None:
                cand, para = chosen
                spare_pos += para.pop("__spare_used__")
                out[lemma] = {"__stem__": cand, **para}
                cursor[cand_len] = i + 1
                break
        else:
            starved += 1
    return out, starved, rejected


# English's own affixes, inflectional AND derivational. An English-ish affix colliding with
# any of these leaks the map -- and `-ly`/`-y` in particular are the model's favorite short
# strings, so they surface immediately if not blocked.
ENGLISH_AFFIXES = set(
    "s es ed d ing er est en n ly y al ial ic ical ish ism ist ity ive ous ious ful less "
    "ness ment tion sion ation able ible age ance ence ancy ency ant ent ure ary ory ery "
    "ize ise ify ate ee or ar eer ian an ward wise like hood ship dom let ling ry fy ty".split()
)


# Letters an affix may not contain. English's own inflections -- `-s -es -ed -ing -er -est` --
# use only s/e/d/i/n/g/r/t, every one a top-10 letter, and its derivational affixes never touch
# j/q/x/z/k/v either. That is not a coincidence: affixes are the most-repeated morphemes in a
# language, so erosion drives them toward the commonest, easiest segments. An unconstrained
# generator has no such pressure and handed us `-ox`, which put an x in every present participle
# (`venerox`, `irredox`) and measurably skewed the letter distribution -- affixes dominate letter
# statistics precisely because they recur on every inflected word.
AFFIX_BANNED_LETTERS = set("jqxzkvw")


def pick_affixes(model: CharNGram) -> dict[str, str]:
    """The regular affix inventory, taken straight from the model's short output.

    Affixes deliberately skip the real-word filter. A bound morpheme never stands alone --
    `-ing` isn't a word and doesn't need to avoid being one. The only real constraint is that
    it not collide with English's OWN affix, or the map leaks.

    And a pleasing inversion falls out: the model's top short strings are exactly the
    affix-shaped debris (`ency`, `aphy`, `lism`, `payshun`) that ruined the stems -- because
    English's real affixes are high-probability endings whose every real instantiation is
    already taken. Terrible stems, ideal affixes. The failure mode becomes the feature.

    PTCP_PST == PST mirrors English's own merger of the regular past and past participle (-ed).

    Affixes must also be mutually distinct. Unconstrained, the model hands back `-fy -ry -by
    -ly` -- all one edit apart, so every inflection would be confusable with every other, and
    the morphology would be unlearnable precisely where it needs to be legible.
    """
    reserved = M.reserved_affixes()
    supply: list[str] = []
    for length in (2, 3, 4):
        for _, cand in model.beam(length, 600):
            if cand in ENGLISH_AFFIXES or cand in reserved:
                continue
            if set(cand) & AFFIX_BANNED_LETTERS:
                continue
            if any(Levenshtein.distance(cand, prev, score_cutoff=2) < 2 for prev in supply):
                continue
            supply.append(cand)
    it = iter(supply)
    pst = next(it)
    affixes = {
        M.PL: next(it),
        M.TSG: next(it),
        M.PST: pst,
        M.PTCP_PST: pst,
        M.PTCP_PRS: next(it),
        M.CMPR: next(it),
    }
    affixes[M.SPRL] = affixes[M.CMPR] + next(it)[:2]  # mirrors -er / -est sharing a stem
    return affixes


def main() -> None:
    print("training on SCOWL 70 (modern, curated, proper names excluded)...")
    lex = list(training_lexicon())
    model = CharNGram(6).train(lex)
    print(f"  {len(lex):,} types")

    print("loading filters (SCOWL95 + wordfreq, 41 foreign langs, tagged blocklist)...")
    filters = Filters()
    print(f"  curated={len(filters.curated):,}  corpus={len(filters.corpus):,} (len>=5 only)  "
          f"foreign={len(filters.foreign):,}  "
          f"blocklist: {len(filters.sub_pats)} substring / {len(filters.exact_pats)} exact")

    print("building English lemma index...")
    ranked, forms = build_lemma_index()
    print(f"  {len(ranked):,} lemmas ranked by summed-form frequency")
    print(f"  top 12: {', '.join(w for w, _ in ranked[:12])}")

    print("generating English-ish stem pool...")
    pool = build_stem_pool(model, filters)
    total = sum(len(v) for v in pool.values())
    print(f"  {total:,} candidates: " + " ".join(f"{L}:{len(pool[L])}" for L in sorted(pool)))

    affixes = pick_affixes(model)
    print(f"  affixes: {'  '.join(f'{k}=-{v}' for k, v in affixes.items())}")

    # Suppletive classes (go/went, be/was) need unrelated stems, not derived ones. Drawn from
    # the long end so they never collide with a real assignment.
    spare = [w for L in (9, 10, 11) for w in pool.get(L, [])[-4000:]]

    print("assigning + realizing (paradigms validated against English's own collisions)...")
    paradigms, starved, rejected = assign(ranked, forms, pool, filters, affixes, spare)
    print(f"  mapped {len(paradigms):,}  starved {starved:,}  "
          f"stems rejected for breaking a paradigm: {rejected:,}")

    words: dict[str, list] = {}
    rank_of = {w: i for i, (w, _) in enumerate(ranked)}
    irregular_hits = 0

    for lemma, _zipf in ranked:
        para = paradigms.get(lemma)
        if para is None:
            continue
        rank = rank_of[lemma]
        stem = para["__stem__"]
        if lemma not in words:
            words[lemma] = [stem, rank]
        if M.class_of(lemma):
            irregular_hits += 1
        for slot, ish in para.items():
            if slot == "__stem__":
                continue
            eng_form = forms.get(lemma, {}).get(slot)
            # Homographs: `saw` is see.PST and saw.N. Highest-frequency lemma wins for v0;
            # disambiguating needs a POS tagger, which is the v1 change.
            if eng_form and eng_form not in words:
                words[eng_form] = [ish, rank]

    payload = {
        "meta": {
            "version": 0,
            "seed": SEED,
            "lemmas": len(paradigms),
            "surface_forms": len(words),
            "irregular_lemmas": irregular_hits,
            "affixes": affixes,
            "known_limits": [
                "stems still contain Latinate affix debris (payshun-class): needs a "
                "derivational morphology database (CELEX/MorphoLex), not a heuristic",
                "candidates ranked by model logprob, which explains only ~16-30% of human "
                "wordlikeness; neighborhood density would be better",
                "homographs collapse to the highest-frequency lemma (no POS tagger yet)",
                "no consonant doubling in sandhi: the rule is stress-conditioned and "
                "generated stems have no stress",
            ],
        },
        "words": words,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"\nwrote {OUT.name}: {len(words):,} surface forms, {kb:,.0f} KB "
          f"({irregular_hits} irregular lemmas mirrored)")


if __name__ == "__main__":
    main()
