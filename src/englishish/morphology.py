"""Inflectional morphology, and mirrored irregularity.

Two strata, and only one is reachable with the data we have:

  * INFLECTIONAL (run->ran, mouse->mice). UniMorph eng covers this: 652k rows, 399k lemmas,
    a clean 10-tag feature set. In scope.
  * DERIVATIONAL (-tion, -ity, -ism, -able). Needs a database that knows BOUND stems --
    `spect`, `struct`, `ceive`, `mit` are not free words, so no "strip if the remainder is a
    word" heuristic can reach them. That's CELEX/MorphoLex/MorphyNet. Out of scope for v0,
    which is why v0 still emits `payshun`-class debris in its stems.

MIRROR, not REGULARIZE. English's irregulars aren't random -- sing/sang/sung, ring/rang/rung
and swim/swam/swum share one i->a->u alternation because they're the residue of Proto-Germanic
ablaut. So we mirror CLASSES, not individual words: each English class gets one English-ish
alternation applied to the same members. English-ish therefore has ablaut, and an English-ish
learner has the same "learn the exceptions" burden a real L2 reader has -- which is part of
the difficulty we're trying to simulate.

The irregular core is curated rather than derived, for two reasons. UniMorph has real gaps
exactly here (`be` absent entirely, `child` has no plural, `find` has no verb forms so no
`found`, and `go` carries a garbage `countable/N;PL` row). And irregularity is preserved *by*
frequency, so the ~150 words below are both tractable to curate and precisely the words the
slider shows at low vocabulary settings.
"""

from __future__ import annotations

from dataclasses import dataclass

VOWELS = "aeiou"

PL, TSG, PST, PTCP_PST, PTCP_PRS, CMPR, SPRL = (
    "PL", "3SG", "PST", "PTCP_PST", "PTCP_PRS", "CMPR", "SPRL"
)
SLOTS = (PL, TSG, PST, PTCP_PST, PTCP_PRS, CMPR, SPRL)

# UniMorph feature tag -> our slot. Its full inventory is only 10 tags.
UNIMORPH_SLOTS = {
    "N;PL": PL,
    "V;PRS;3;SG": TSG,
    "V;PST": PST,
    "V;V.PTCP;PST": PTCP_PST,
    "V;V.PTCP;PRS": PTCP_PRS,
    "ADJ;CMPR": CMPR,
    "ADJ;SPRL": SPRL,
}


# --------------------------------------------------------------- shape helpers

def first_vowel_span(s: str) -> tuple[int, int] | None:
    i = 0
    while i < len(s) and s[i] not in VOWELS:
        i += 1
    if i >= len(s):
        return None
    j = i
    while j < len(s) and s[j] in VOWELS:
        j += 1
    return i, j


def swap_vowel(s: str, v: str) -> str:
    """Replace the first vowel span.

    English ablaut targets the *stressed root* vowel; for a monosyllabic stem that's the only
    vowel, and for a generated stem we have no stress information (CMUdict encodes stress in
    a digit, but our stems aren't in CMUdict). First-vowel is a consistent proxy, and
    consistency is what makes it learnable.
    """
    span = first_vowel_span(s)
    if span is None:
        return s
    i, j = span
    return s[:i] + v + s[j:]


def strip_coda(s: str) -> str:
    """Everything up to and including the last vowel span."""
    k = len(s)
    while k > 0 and s[k - 1] not in VOWELS:
        k -= 1
    return s[:k] if k else s


def join(stem: str, affix: str) -> str:
    """English's orthographic joins, minus the one that needs stress.

    Consonant doubling (run -> running) is conditioned on STRESS, not on a CVC pattern --
    applying it by pattern gives `hered` + `-ashun` -> `hereddashun`. We have no stress for
    generated stems, so we omit doubling rather than misapply it.
    """
    if not affix:
        return stem
    if affix[0] in VOWELS and stem and stem[-1] in VOWELS:
        stem = stem[:-1]          # nature + al -> natural; also kills glea+ah -> gleaah
    elif affix[0] not in VOWELS and stem.endswith("y"):
        stem = stem[:-1] + "i"    # happy + ness -> happiness
    return stem + affix


# --------------------------------------------------------------- rules

@dataclass(frozen=True)
class Rule:
    """How an English-ish irregular class realizes one slot."""

    vowel: str | None = None      # replace first vowel span
    suffix: str = ""              # append
    replace_coda: str | None = None  # replace the trailing consonant cluster
    zero: bool = False            # unchanged (sheep/sheep, cut/cut)
    suppletive: bool = False      # an independently generated stem

    def apply(self, stem: str) -> str:
        if self.zero:
            return stem
        out = stem
        if self.replace_coda is not None:
            return strip_coda(out) + self.replace_coda
        if self.vowel is not None:
            out = swap_vowel(out, self.vowel)
        return join(out, self.suffix) if self.suffix else out


Z = Rule(zero=True)
SUP = Rule(suppletive=True)


# --------------------------------------------------------------- the classes
#
# Each entry: English exemplar -> English-ish alternation for the affected slots.
# Membership mirrors English exactly; the alternation is arbitrary but consistent.

VERB_CLASSES: dict[str, dict[str, Rule]] = {
    # sing/sang/sung -- Germanic strong class III. Three-way ablaut.
    "ablaut_i_a_u": {PST: Rule(vowel="o"), PTCP_PST: Rule(vowel="u")},
    # drive/drove/driven
    "ablaut_i_o_i": {PST: Rule(vowel="ai"), PTCP_PST: Rule(vowel="i", suffix="en")},
    # break/broke/broken
    "ablaut_ea_o_o": {PST: Rule(vowel="oo"), PTCP_PST: Rule(vowel="oo", suffix="en")},
    # take/took/taken
    "ablaut_a_oo_a": {PST: Rule(vowel="ee"), PTCP_PST: Rule(suffix="en")},
    # know/knew/known
    "ablaut_ow_ew_own": {PST: Rule(vowel="ue"), PTCP_PST: Rule(suffix="on")},
    # find/found/found -- past and participle merged
    "ablaut_i_ou_ou": {PST: Rule(vowel="au"), PTCP_PST: Rule(vowel="au")},
    # bring/brought -- coda replacement, past == participle
    "ought": {PST: Rule(replace_coda="acht"), PTCP_PST: Rule(replace_coda="acht")},
    # keep/kept -- vowel shortening plus -t
    "ept": {PST: Rule(vowel="e", suffix="t"), PTCP_PST: Rule(vowel="e", suffix="t")},
    # build/built -- final d -> t
    "dental_t": {PST: Rule(replace_coda="t"), PTCP_PST: Rule(replace_coda="t")},
    # cut/cut/cut -- zero marking
    "zero_pst": {PST: Z, PTCP_PST: Z},
    # go/went/gone -- suppletion
    "suppletive_v": {PST: SUP, PTCP_PST: SUP},
}

VERB_MEMBERS: dict[str, str] = {}
for _cls, _words in {
    "ablaut_i_a_u": "sing ring spring swim drink shrink sink stink begin",
    "ablaut_i_o_i": "drive ride rise write strive thrive smite",
    "ablaut_ea_o_o": "break speak steal freeze choose weave wake bear tear swear wear",
    "ablaut_a_oo_a": "take shake forsake mistake",
    "ablaut_ow_ew_own": "know grow throw blow fly draw slay",
    "ablaut_i_ou_ou": "find bind grind wind",
    "ought": "bring buy think seek catch teach fight",
    "ept": "keep sleep sweep weep creep feel kneel mean deal leave lose",
    "dental_t": "build send spend bend lend",
    "zero_pst": "cut put set let hit shut cost hurt quit split spread cast burst bet",
    "suppletive_v": "go be do have stand understand see eat give take come run make say",
}.items():
    for _w in _words.split():
        VERB_MEMBERS[_w] = _cls

NOUN_CLASSES: dict[str, dict[str, Rule]] = {
    # man/men, foot/feet -- i-umlaut
    "umlaut": {PL: Rule(vowel="ee")},
    # child/children, ox/oxen
    "en_plural": {PL: Rule(suffix="ern")},
    # sheep/sheep
    "zero_plural": {PL: Z},
    # leaf/leaves -- f -> v + es
    "ves": {PL: Rule(replace_coda="vez")},
    # cactus/cacti
    "latin_i": {PL: Rule(replace_coda="ai")},
    # analysis/analyses
    "latin_es": {PL: Rule(replace_coda="eez")},
    # criterion/criteria, datum/data
    "latin_a": {PL: Rule(replace_coda="a")},
    # index/indices
    "latin_ices": {PL: Rule(replace_coda="ithez")},
}

NOUN_MEMBERS: dict[str, str] = {}
for _cls, _words in {
    "umlaut": "man woman foot tooth goose mouse louse",
    "en_plural": "child ox brother",
    "zero_plural": "sheep deer fish series species aircraft salmon trout moose offspring",
    "ves": "leaf wolf knife life wife half shelf thief calf loaf",
    "latin_i": "cactus fungus radius nucleus alumnus stimulus syllabus",
    "latin_es": "analysis crisis thesis basis hypothesis diagnosis parenthesis",
    "latin_a": "criterion phenomenon datum medium bacterium curriculum",
    "latin_ices": "index appendix matrix vertex",
}.items():
    for _w in _words.split():
        NOUN_MEMBERS[_w] = _cls

ADJ_CLASSES: dict[str, dict[str, Rule]] = {
    "suppletive_adj": {CMPR: SUP, SPRL: SUP},
}
ADJ_MEMBERS = {w: "suppletive_adj" for w in "good bad far little much many".split()}

IRREGULAR: dict[str, str] = {**VERB_MEMBERS, **NOUN_MEMBERS, **ADJ_MEMBERS}
ALL_CLASSES: dict[str, dict[str, Rule]] = {**VERB_CLASSES, **NOUN_CLASSES, **ADJ_CLASSES}


def class_of(lemma: str) -> str | None:
    return IRREGULAR.get(lemma)


def reserved_affixes() -> frozenset[str]:
    """Strings the irregular classes already use.

    The regular affix inventory must avoid these or the paradigm collapses: with `-on` as both
    the 3SG affix and the ablaut_ow_ew_own participle, `knows` and `known` both realize as
    `elidon` and the distinction is simply gone.
    """
    out: set[str] = set()
    for slots in ALL_CLASSES.values():
        for rule in slots.values():
            if rule.suffix:
                out.add(rule.suffix)
            if rule.replace_coda:
                out.add(rule.replace_coda)
    return frozenset(out)


def realize(stem: str, lemma: str, slot: str, regular_affixes: dict[str, str]) -> str | None:
    """The English-ish surface form of `lemma` in `slot`, given its English-ish stem.

    Irregular classes win; everything else takes the regular affix.
    """
    cls = class_of(lemma)
    if cls is not None:
        rule = ALL_CLASSES[cls].get(slot)
        if rule is not None:
            if rule.suppletive:
                return None  # caller supplies an independently generated stem
            return rule.apply(stem)
    affix = regular_affixes.get(slot)
    if affix is None:
        return None
    return join(stem, affix)
