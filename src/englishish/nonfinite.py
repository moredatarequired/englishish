"""Non-finite verb forms English doesn't have.

English's non-finite inventory is thin: bare infinitive, `to`-infinitive, present participle,
past participle. That's it. Most of the world's languages carry more, and the gaps English leaves
are filled by clumsy periphrasis -- `in order to sing`, `having sung`, `while singing`, `tried to
sing but didn't`.

Two design principles, both borrowed from how this actually happens in real languages:

1. NEW FORMS GRAMMATICALIZE FROM EXISTING PERIPHRASIS. You don't invent a supine out of nothing;
   a language fuses `for to X` into a suffix. English is visibly mid-process already -- `going to`
   -> `gonna`, `want to` -> `wanna`, `have to` -> `hafta`. English-ish is just English that took
   the next step. That's what makes these maximally English-ish rather than arbitrary.

2. THE BASE STEM DETERMINES WHETHER IRREGULARITY PROPAGATES. This is the interesting part, and
   it's why Latin verbs are taught with "principal parts": the Latin supine is built on the
   perfect-participle stem (`amat-um` from `amatus`), so it inherits every irregularity that stem
   has. Swedish's supine simply *is* the perfect participle. So a new form's base is a real
   decision with visible consequences -- build it on the participle and `sing` gets an irregular
   supine while `walk` doesn't; build it on the present stem and everything stays regular.

   We split them across bases deliberately, which gives English-ish a present-stem group and a
   past-stem group. Very Indo-European.

WHY THESE CAN'T LIVE IN lexicon.json, which is the genuinely interesting consequence: the shipped
artifact maps `english_wordform -> englishish_wordform`. These forms have NO English wordform to
key on -- English needs a whole construction to say them. So going English -> English-ish stops
being substitution and becomes *translation*: you'd have to recognise `in order to sing` as a
purposive and collapse three words into one. Adding a form English lacks breaks the word-for-word
bijection in the other direction.
"""

from __future__ import annotations

from . import morphology as M

PRESENT, PAST, PARTICIPLE = "PRESENT", "PAST", "PARTICIPLE"

# slot -> (base stem, gloss, what English has to say instead, what it grammaticalized from)
NONFINITE: dict[str, tuple[str, str, str, str]] = {
    "SUPINE": (
        PARTICIPLE,
        "purposive / supine",
        "(in order) to X",
        "`for to X` -- still alive in Scots/Appalachian English",
    ),
    "CONVERB_SIM": (
        PRESENT,
        "simultaneous converb",
        "while X-ing",
        "`while X-ing` with the subordinator fused",
    ),
    "CONVERB_SEQ": (
        PARTICIPLE,
        "sequential converb",
        "having X-ed, ...",
        "`having X-ed` with the auxiliary fused",
    ),
    "FRUSTRATIVE": (
        PAST,
        "frustrative",
        "X-ed in vain / tried to X and failed",
        "`X-ed for nothing`",
    ),
    "AVERTIVE": (
        PAST,
        "avertive",
        "almost X-ed / was about to X but didn't",
        "`was about to X`",
    ),
}


def base_form(
    stem: str, lemma: str, base: str, affixes: dict[str, str]
) -> str | None:
    """The form a non-finite is built on.

    For an irregular, the PAST/PARTICIPLE base is already ablauted, so the new form inherits the
    alternation for free -- `sing`/`sang`/`sung` -> the supine is built on the `sung` counterpart
    and carries its vowel. For a regular, the base is stem+affix, so the new form is predictable.
    That asymmetry is the point: principal parts.
    """
    if base == PRESENT:
        return stem
    slot = M.PST if base == PAST else M.PTCP_PST
    return M.realize(stem, lemma, slot, affixes)


def paradigm(
    stem: str, lemma: str, affixes: dict[str, str], nf_affixes: dict[str, str]
) -> dict[str, str]:
    """Every non-finite form English lacks, for one English-ish stem."""
    out: dict[str, str] = {}
    for slot, (base, _gloss, _eng, _from) in NONFINITE.items():
        b = base_form(stem, lemma, base, affixes)
        if b is None:  # suppletive -- needs its own stem, same as go/went
            continue
        out[slot] = M.join(b, nf_affixes[slot])
    return out
