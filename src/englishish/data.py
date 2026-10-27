"""Data loading. Every source here was verified live 2026-07-15; see FINDINGS.md.

Deliberate choices:
  * SCOWL 70 lowercase-only for training -- modern (has internet/email/selfie/emoji) and
    proper names live in separate capitalized entries we can drop. NOT /usr/share/dict/web2,
    which is Webster's Second International (1934): no `internet`, but it does have
    `zyzzogeton`, and it errs in the worst direction -- it would ship real words as invented.
  * SCOWL 95 union wordfreq-en for the real-word oracle. ~805k; ENABLE adds only 168 words
    over this, so it's skipped.
  * wordfreq is frozen at 3.1.1 (2023-11), not abandoned -- the author stopped because
    "Generative AI has polluted the data". For us the freeze is a feature: we want human
    word frequencies, so a pre-2022 snapshot is exactly right.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import cache
from pathlib import Path

from wordfreq import top_n_list

DATA = Path(__file__).resolve().parents[2] / "data"

WORD_RE = re.compile(r"[a-z]{2,}")

# wordfreq's languages minus English, and minus every non-Latin script.
#
# Our candidates are a-z by construction, so a non-Latin-script language can only contribute
# romanizations -- which is not what a reader would recognise as "a Japanese word" anyway. Dropping
# them also sidesteps a real gotcha: zipf_frequency() TOKENIZES, and ja/ko/zh need the
# `wordfreq[cjk]` extra (MeCab) to do it, so scoring them raises ModuleNotFoundError. top_n_list()
# doesn't tokenize, which is why this only surfaced once a frequency floor was added.
#
# The foreign-collision check is a ~0.04% filter overall (~0.1% at >=7 chars) -- deliberately cheap.
FOREIGN_LANGS = (
    "es fr de it pt nl sv pl id tr cs da fi nb ro hu ca hr lt lv sk sl ms fil is"
).split()


@cache
def training_lexicon() -> tuple[str, ...]:
    """SCOWL 70, lowercase a-z only. What English words look like."""
    path = DATA / "scowl70.txt"
    words = {ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()}
    return tuple(sorted(w for w in words if WORD_RE.fullmatch(w)))


# Below this length, wordfreq carries ~no information about wordhood -- see is_real_word().
# 4, not 5: at length 4 wordfreq claims only 5.61% of the space, so consulting it costs ~5% of a
# 456,976-candidate pool (irrelevant) and it catches modern vocabulary the dictionaries miss --
# `yeet` slipped through at a floor of 5. At lengths 2-3 it claims 100% / 65% and must be ignored.
CORPUS_ORACLE_MIN_LEN = 4


@cache
def curated_words() -> frozenset[str]:
    """DICTIONARY oracle: SCOWL 95 + web2. Answers "is this an English word?"

    web2 is included here even though it's disqualified for training. Its bias is archaism, and
    for pruning that's the *safe* direction: an archaic entry catches one more real word. The
    error that matters is shipping a real word as invented, and web2 only reduces it. Training is
    the opposite -- there its bias becomes our model's bias.
    """
    scowl = {
        ln.strip().lower()
        for ln in (DATA / "scowl95.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    }
    web2: set[str] = set()
    web2_path = Path("/usr/share/dict/web2")
    if web2_path.exists():
        web2 = {
            ln.strip().lower()
            for ln in web2_path.read_text(encoding="utf-8", errors="replace").splitlines()
        }
    return frozenset({w for w in scowl | web2 if w and w.isalpha()})


@cache
def corpus_words() -> frozenset[str]:
    """CORPUS oracle: wordfreq. Answers "does this string appear in English text?"

    A different question from wordhood, and only usable as a proxy for it above a length floor.
    Kept separate from curated_words() precisely so the two aren't confused again.
    """
    return frozenset(w for w in top_n_list("en", 300_000) if w.isalpha())


def is_real_word(w: str) -> bool:
    """Is `w` already English?

    ---------------------------------------------------------------------------------------
    TWO ORACLES, TWO DIFFERENT QUESTIONS. Conflating them was a real bug that shipped.

    wordfreq answers "does this string OCCUR in English text?" -- so it contains every
    abbreviation, initialism, OCR artifact, tokenization fragment and transliteration that ever
    appeared. SCOWL and web2 are curated dictionaries; they answer "is this a WORD?"

    Using wordfreq for wordhood produced the claim "there are ZERO free 2-letter strings", which
    then hardened into a design constraint (1- and 2-letter English words *must* get longer
    English-ish counterparts). It was an artifact. Measured:

        oracle                      free 2-letter   free 3-letter
        wordfreq only                     0              611
        SCOWL 95 + web2 (curated)        33            2,727     <- 4.5x the pool at length 3

    An oracle that says yes to everything carries zero information. wordfreq claims
    100.00% / 65.08% / 5.61% / 0.34% of the space at lengths 2/3/4/5 -- literally 0 bits at
    length 2. From length 4 it becomes informative AND starts contributing real modern vocabulary
    the curated dictionaries miss (`yeet` is in wordfreq, in neither SCOWL 95 nor web2), while
    costing only ~5% of a 456,976-candidate pool. So the floor is 4.

    So: dictionaries always; corpus only where it carries information.
    ---------------------------------------------------------------------------------------
    """
    if w in curated_words():
        return True
    return len(w) >= CORPUS_ORACLE_MIN_LEN and w in corpus_words()


@cache
def unimorph() -> dict[str, tuple[tuple[str, str], ...]]:
    """lemma -> ((form, features), ...) from UniMorph eng.

    Known gaps, verified: `be` is entirely absent; `child` has no plural; `find` has no verb
    forms (so no `found`); and `go` carries a garbage `countable/N;PL` row from a Wiktionary
    parse error. So this is used for the REGULAR bulk only -- the irregular core is curated
    in morphology.py, which is safe because irregularity is preserved *by* frequency and
    therefore concentrated in a couple hundred common words.
    """
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    path = DATA / "unimorph_eng.tsv"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        lemma, form, feats = parts
        if not (lemma.islower() and form.islower()):
            continue
        out[lemma].append((form, feats))
    return {k: tuple(v) for k, v in out.items()}


@cache
def blocklist() -> tuple[frozenset[str], frozenset[str]]:
    """(substring_patterns, exact_patterns) for profanity/slur filtering.

    The cost asymmetry inverts versus normal moderation. There, a false positive silences a
    real person, so you favor precision. Here a false positive discards one candidate from an
    infinite generator -- cost ~zero -- while a false negative means the toy emits a slur. So
    we favor RECALL. Reclamation depends on speaker identity, which a generator categorically
    lacks, so reclaimed terms are blocked rather than exempted; there is no speaker to silence.

    But substring matching over-blocks ~5x more than edit-distance-1 (2.21% vs 0.46% of real
    English), driven entirely by short stems: `ass` hits bass/mass/class, `tit` hits
    petit/title, `anal` hits banal/canal, `rape` hits grape/therapeutic. So substring matching
    is restricted to LONG, high-severity, unambiguous stems; everything else is exact-match.
    """
    subs: set[str] = set()
    exact: set[str] = set()

    dso = json.loads((DATA / "dsojevic_en.json").read_text(encoding="utf-8"))
    for entry in dso:
        severity = entry.get("severity", 0)
        for pat in entry.get("match", "").split("|"):
            pat = re.sub(r"[^a-z]", "", pat.lower())
            if len(pat) < 3:
                continue
            exact.add(pat)
            # Only substring-match stems long enough not to be a coincidence.
            if severity >= 3 and len(pat) >= 5:
                subs.add(pat)

    for line in (DATA / "ldnoobw_en.txt").read_text(encoding="utf-8").splitlines():
        pat = re.sub(r"[^a-z]", "", line.strip().lower())
        if len(pat) >= 3:
            exact.add(pat)
            if len(pat) >= 5:
                subs.add(pat)

    # Long, unambiguous stems worth catching inside longer strings. `interrorist` and
    # `masturbed` both escaped an exact-match-only filter on the first spike run.
    # Long, unambiguous stems worth catching inside longer strings, curated because the
    # off-the-shelf lists miss them. Every entry here is one the pipeline actually emitted or
    # nearly emitted: `masturbed` and `interrorist` escaped an exact-match-only filter on the
    # first spike run, and `leaf -> clitor` shipped in the first real build.
    subs |= {
        # sexual / anatomical -- the category that actually fires, because these stems are
        # phonotactically ordinary and sit right where the generator likes to be.
        "fuck", "cunt", "clitor", "clit", "vagin", "penis", "peni", "scrotum", "testicl",
        "semen", "cum", "jizz", "ejacul", "masturb", "orgasm", "erecti", "phallus", "phallic",
        "anus", "anal", "rectum", "genital", "labia", "vulva", "nipple", "prostat", "sperm",
        "porn", "fellat", "cunnil", "sodom", "incest", "bestial", "necroph", "pedo", "paedo",
        "molest", "rape", "rapist", "slut", "whore", "hooker", "prostitut",
        # slurs. Blocked, not exempted: reclamation depends on speaker identity, and a
        # generator has none -- there is no speaker to silence, so recall wins outright.
        "nigg", "chink", "kike", "spic", "wetback", "gook", "coon", "dago", "honky",
        "faggot", "fagg", "dyke", "tranny", "shemale", "retard", "spastic", "mongoloid",
        "cripple", "midget",
        # atrocity / self-harm
        "nazi", "hitler", "genocid", "holocaust", "lynch", "slaver", "terror", "jihad",
        "suicid", "selfharm", "anorexi", "bulimi",
        # scatological
        "shit", "turd", "feces", "faeces", "urinat", "defecat", "piss", "crap", "fart",
        # vulgar. Only stems with no innocent host: `asshole` is safe as a substring, bare `ass`
        # is not (bass/mass/class), and `arse` is not (coarse/sparse/hoarse).
        "wank", "twat", "bollock", "bugger", "asshole", "arsehole", "dumbass", "jackass",
        "dickhead", "cocksuck", "motherfuck", "bullshit", "goddam",
    }
    return frozenset(subs), frozenset(exact)
