# English-ish: empirical findings

## Short replacements were unnatural, and the cause was a selection effect

Caught by Hugh reading output: `regelative`, `uncer`, `pretting` read as English; `kry`, `ple`,
`hoic` were *plausible but not natural*. Hypothesis offered: we over-value short strings because
every extra character lowers probability, so poor fit gets compensated and rare letters slip in.
Proposed check: preserve the 1-gram (letter) distribution over large blocks of text.

**Right about where, and the check worked. The mechanism was different and worse.** Ranking is
length-stratified, so length can't confound it. The real cause:

| length | of 17,576 strings | rare-letter mass (jqxzkvwy) |
|--------|------------------|----------------------------|
| real English 3-letter words | 2,386 | **12.7%** |
| free 3-letter strings | 15,190 | **33.6%** — 2.6× enriched |

**English took the common-letter strings.** Rejecting real words leaves a residual systematically
enriched in rare letters. Ranking by logprob pulled our selected length-3 words from 33.6% down to
10.6% — real work — but could never reach English's 6.5%, because the good strings are *gone*. **No
re-ranking fixes a bucket that's been picked clean.** Measured, the bias was length-dependent
exactly as predicted: 1.6× at length 3, 2.0× at length 4, and gone (0.7–1.2×) from length 5 up.

**Fix: refuse to draw below length 5**, plus a per-length naturalness floor (within 0.3 nats/char of
a real English word *of the same length* — per-char logprob is strongly length-dependent, rising
from −3.92 at length 2 to −1.17 at length 11, so an absolute floor would reject real 3-letter
English). Starving the short buckets wasn't enough on its own: the floor left exactly 9 candidates
at length 3, and the 9 commonest English words consumed all 9.

The cost is longer words, and it's worth paying — Zipf's law of abbreviation is ρ≈0.12 (1.5% of
variance) and it *saturates*, so per-word length matching was a worthless constraint being enforced
at the price of the one thing a reader can see. Mean length 6.99 → 7.81 (+12%).

| | before | after |
|---|---|---|
| the | `ble` | **`hered`** |
| of | `acy` | **`inges`** |
| i | `chy` | **`pread`** |
| is | `aed` | **`lique`** |
| for | `ced` | **`uncer`** |

**And the check caught a second defect: our own affix.** `-ox` as the present participle put an x in
every participle (`venerox`, `irredox`). Affixes dominate letter statistics because they recur on
every inflected word — **which is why English's own inflections (`-s -es -ed -ing -er -est`) use
nothing but top-10 letters.** That's not coincidence: affixes are the most-repeated morphemes, so
erosion drives them toward the commonest segments. An unconstrained generator has no such pressure.
Banning `jqxzkvw` from the affix inventory moved x from **1.4× over-used to 0.63× under-used**.

**Result** (vocab 2,000, 18% of running text replaced): y 1.4→1.3×, x 1.4→0.63×, TV distance
0.057→0.050, and every replacement length now sits at 0.5–1.1× English's rare-letter mass.

⚠️ **Ratios mislead on rare letters.** z at 1.5× of English's 0.07% is an excess of 0.035pp. w at
0.52× of 2.4% is a **deficit of 1.2pp — 34× larger**. The residual divergence is now *under*-use of
w/j/k/f (0.47–0.76×), because the naturalness floor over-corrects: words carrying those letters have
lower logprob and get cut. That's the next thing to fix if anyone cares, and it argues for targeting
the letter distribution directly rather than via a logprob proxy.

## What v0 taught that the spikes couldn't

Four findings that only appear once you actually build the thing. See [README.md](README.md) for
the architecture.

### 1. EXISTENCE PROVES NOTHING — the same error, FIVE times
Any categorical "is X attested?" test against a large word list returns **True** almost always,
because these lists have enormous junky tails. It bit five times in five costumes:

| the test | what the junk did |
|----------|------------------|
| "is the remainder a word?" (derivational stripper, spike 5) | `international = tern + -ational + in-` — *tern*, the seabird. `between = twee + be- + -en`. `president = side + -ent + pre-`. |
| "is this consonant cluster attested?" (v0 pronounceability) | **`mzee`** — one word — legalized the `mz-` onset, so `it → mze`. `dziggetai` legalized `dz-` (`i → dzu`). The abbreviation **`hdqrs`** legalized `hd-` (`dog → hdy`). |
| "≥12 attesting types?" | bare `q-` scraped exactly **14** — all Arabic/Chinese loanwords, *inflated by inflection* (`qadi/qadis`, `qibla/qiblah/qiblas` are two lemmas, not five words). So `in → qir`, `i → qab`. |
| **"is this an English word?" via wordfreq** | Produced the claim **"there are ZERO free 2-letter strings"**, which hardened into a design constraint. Artifact: wordfreq is a *corpus* list, so it contains every abbreviation and OCR fragment ever printed. It claims **100.00%** of the 2-letter space — literally 0 bits. |
| **"is this a word in language L?" via wordfreq, ×41** | Reported **`eb` as a word in French, German, Spanish, Italian, Dutch, Portuguese, Swedish, Polish AND Turkish**, and killed the entire remaining 2-letter pool on that basis. |

The fix is always the same: require **frequency-weighted** evidence, not existence — and make sure
the oracle answers the question you're actually asking. This generalizes well past this project:
any data-derived categorical inventory is unsafe by default.

### 1b. "Zero free 2-letter strings" was FALSE, and it was load-bearing
Caught by Joshua asking, reasonably, on what basis `ot`/`ei`/`ib` were being excluded. They aren't
English words in any sense a reader would notice. Measured, by oracle:

| oracle for "is this a word?" | free 2-letter | free 3-letter |
|------------------------------|---------------|---------------|
| wordfreq only (what shipped) | **0** | 611 |
| SCOWL 95 + web2 (curated dictionaries) | **33** | **2,727** |

**Three distinct oracle bugs were stacked here**, and it took all three to make the space look full:

1. **wordfreq is a frequency list, not a dictionary.** It answers "does this string OCCUR in English
   text?", not "is this a WORD?". `ot` (occupational therapy) and `ib` (International Baccalaureate)
   sit at zipf 3.85 and 3.45 — so a *frequency floor doesn't help*; only the right oracle does. This
   project used wordfreq for ranking (correct) and wordhood (wrong). Fix: dictionaries always,
   corpus only at length ≥4 where it stops being saturated (100%/65%/5.6%/0.34% at lengths 2/3/4/5)
   and starts contributing real modern vocabulary the dictionaries miss (`yeet` is in wordfreq and
   in neither SCOWL 95 nor web2).
2. **The foreign check had the same disease, ×41.** `top_n_list(lang, N)` is also a corpus list.
   Unfloored it called `eb` a word in nine languages.
3. **Even a *correct* foreign oracle kills the space — because the question was wrong.** `eb` really
   is Dutch for "ebb" (zipf 3.48); `ek`, `ig`, `ub` likewise. So a correct Dutch-wordhood oracle
   correctly kills all 33 candidates. But the filter's actual job is *"would an English reader
   recognise this as foreign?"* — and nobody clocks `eb` as Dutch. It exists to stop
   `hola`/`merci`/`danke`, which need ≥4 characters to be recognisable. **Match the oracle to the
   question you're asking**, not to the nearest question you have data for.

**The payoff was the single biggest quality win in v0** — the function words, which were the worst
thing about it:

| | before | after |
|---|---|---|
| the | `ghy` | **`ble`** |
| to | `xys` | **`ze`** |
| of | `ixt` | **`vy`** |
| a | `zof` | **`ix`** |
| in | `fyl` | **`py`** |
| i | `eyr` | **`ek`** |
| is | `xus` | **`ku`** |
| on | `axy` | **`ke`** |

And length matching now holds at the short end (`of`→`vy`, `on`→`ke`), which it structurally could
not before. **A false "impossibility" finding had been suppressing the fix for it.** The lesson:
when a measurement says something is impossible, check the measurement's oracle before designing
around the impossibility.

### 1c. A leak scan can only find what's in its blocklist
`pissoids` shipped while the scan reported **0 leaks** — because `piss` wasn't in the list. The scan
is not an independent check; it's the blocklist re-asked. Reading actual output caught what the
automated scan structurally couldn't.

### 2. The blocklist must run on COMPOSED forms, not just on stems
`leaf → clitor` shipped in the very first real build — the ship-blocker landing exactly where
predicted. But the deeper version showed up only after the stems were clean: **52 leaks, every one
composed rather than generated.**

- `apped` + PTCP_PRS `-ox` → `appedox` — contains "pedo". Same for `epedox`, `ipedox`, `stapedox`, `hampedox`, `rupedox`.
- `luxurian` + 3SG `-us` → `luxurianus` — contains "anus". Same for `oliganus`, `extranus`, `amianus`, `diamanus`, `inyanus`.

Every stem involved passed the filter. **The affix did it.** Filtering generator output is
insufficient; affixation manufactures new strings, so the check has to run post-composition.

### 3. English collides N;PL with V;3SG for every noun-verb homograph — and that's orthographic accident
`walk` → `walks` twice (plural noun *and* 3rd-person-singular verb). English-ish uses distinct
plural and 3SG affixes, so it never collides them. Requiring English-ish to inherit that collision
rejects `walk`, `run`, `look`, `work` and most of the language — the build hung until paradigm
signatures were compared *within* a part of speech rather than across. It's spelling coincidence,
not structure. (This is the "should English-ish inherit English's homographs?" question, answered
concretely: no.)

### 4. Faithfulness beats distinctness
`sing → ught` looks fine until you notice the stem opens with its own vowel, so the i→a→u ablaut is
a no-op and `sung` also comes out `ught`. But you can't just demand all forms differ — that would
over-differentiate every regular verb, where English itself collapses past and participle
(`walk/walked/walked`). The right constraint is that **English-ish forms collide exactly where
English's forms collide**: compare the paradigm's collision signature. 14.9M candidate stems get
rejected this way per build.

### Also worth knowing
- **SCOWL 70 fixes the web2 problem outright**: 126,753 lowercase entries, proper names in separate
  capitalized entries, and all of `internet/email/blog/website/app/laptop/podcast/selfie/emoji/teenager`
  present. Its wordlist-generator API (`app.aspell.net/create`) is live and beats the tarball.
- ⚠️ **The real-word union is ~575k, not the ~805k a research pass predicted.** SCOWL's create API at
  `max_size=95` yields ~303k, not the ~644k reported for "size 95" from the tarball (which likely
  summed proper-name/abbreviation files and duplicate size tiers). Recorded rather than papered over.
- **Affixes should skip the real-word filter entirely.** A bound morpheme never stands alone — `-ing`
  isn't a word and needn't avoid being one. They *do* need to avoid English's own affixes (`-ly`
  surfaced immediately otherwise, leaking the map) and each other: unconstrained, the model hands
  back `-fy -ry -by -ly`, all one edit apart, making every inflection confusable with every other.
- **The debris is perfect for affixes.** The model's top short non-words are affix-shaped
  (`ency`, `aphy`, `lism`, `payshun`) *precisely because* English's real affixes are high-probability
  endings whose every real instantiation is taken. Terrible stems, ideal affixes. The failure mode
  becomes the feature.
- **Sandhi needs stress we don't have.** Consonant doubling is stress-conditioned, not CVC-conditioned:
  applying it by pattern gives `hered + -ashun → hereddashun`. Omitted rather than misapplied — one
  more reason spike 4 shouldn't have stripped CMUdict's stress digits.

---

# Findings from the spikes

Three throwaway spikes (`scratchpad/spike.py`, `spike2.py`, `spike3.py`) run against a
character n-gram trained on `wordfreq` ∩ `/usr/share/dict/web2`. Everything below is
measured, not assumed. Numbers are reproducible with seed `0xE4611`.

## The concept works

At "you know the top 300 English words", Pride & Prejudice reads:

> It is a **flect** universally acknowledged, that a **unment** man in **pragmation** of a
> good **scratic**, must be in want of a **ratic**. However little **creet** the **mighting**
> or **dhone** of such a man may be on his first **kindless** a neighbourhood, this **flect**
> is so well **insey** in the **porrid** of the **interrorist** **efficial** …

That is the target experience, and it fell out of ~200 lines. The core loop
(frequency-ranked English ↔ frequency-ranked pseudowords, swap by rank) is sound.

Measured token coverage: vocab 1,000 → 71%, 3,000 → 77%, 10,000 → 89%.

⚠️ I originally wrote that these "match the lexical-coverage literature." **They don't, and the
comparison is category-confused.** Our slider ranks **types** (surface wordforms). Nation
counts **word families** (stem + inflections + 80+ derivational affixes — `nation` absorbs
`internationalisation`). One family expands to many types, so our top-1,000-*types* → 71% is
consistent with, but not comparable to, Nation's top-1,000-*families* → 78–81%. Any UI label
quoting the literature's numbers against a type-ranked slider is simply wrong. Pick a unit and
say which. (Related: my "2,000 families ≈ 80%" recollection was off by ~2× — it's **1,000**
families ≈ 78–81%; 2,000 ≈ 86–89%. The low end of the slider is twice as brutal as advertised.)

## Settled by measurement

### Type-weighting beats token-weighting, decisively
Training the n-gram weighted by corpus frequency produces a model that just regenerates
common English: **95.2% of samples collided with real words** (vs 21.6% type-weighted), the
survivors were blends of frequent words (`courself`, `accountry`, `becaused`, `universion`),
and the length-vs-logprob gradient went flat (9.0→9.6 across deciles, i.e. no signal).
Type-weight the generator. Use token frequency only for the *mapping*.

### `wordfreq`'s top-60k is heavily polluted with proper nouns
Untreated, the model emits `galileemf`, `bylonishikon`, `vargaminorah`, `gdprkurdion`,
`xinjimpost`, `philipping`, `jimenezer`. Intersecting with web2's lowercase-only entries
drops **45,116 of 75,445** types and fixes it. Cost: loses post-1934 vocabulary
(`internet`, `email`). Acceptable for learning word *shape*; revisit if it bites.

### The monotone zip does NOT preserve length for free
I assumed shorter strings have higher logprob (they do), so ranking by logprob would
reproduce Zipf's law of abbreviation automatically. **Wrong.** Generated mean length 8.85
vs English 7.2, and the naive zip maps `the → disting`. Fix: **stratify the map by length**
and hold monotonicity *within* each length bucket. This is a refinement, not a compromise —
length is part of what makes a frequent word plausible, so stratifying serves the goal
(English-ish self-consistent as a language) better than global monotonicity does.

### "Far from every real word" is unsatisfiable; "far from its own source" is the real constraint
100% of length ≤4 non-words sit within edit distance 1 of a real English word; 96.7% at
length 5; 88.3% at 6. So the anti-typo constraint cannot be "unlike all English". It must be
"unlike the word it replaces" — which is cheap, and is what actually prevents the map
feeling like a spelling error.

### How full is the space? Count the MASS, not the strings

My first pass reported "94.1% of the length-4 space is free" using 26⁴ as the denominator.
**That number is worthless** — it counts `xqzk` and `bfag` as free space. The space is
defined by phonotactic constraint, so the only meaningful denominator is *probability mass*.

Recomputed exactly, length-4 orthographic: 94.5% free **by count**, but real English holds
**97.9% of the probability mass** — only **2.1%** is actually available. Off by ~45×.

Phoneme space (exact enumeration, 39-phone ARPAbet inventory, model trained on 26,574 clean
common words):

| phonemes | sequences | real words | mass claimed by English | available |
|----------|-----------|-----------|-------------------------|-----------|
| 2        | 1,521     | 387       | **98.2%**               | 1.8%      |
| 3        | 59,319    | 3,725     | **94.5%**               | 5.5%      |
| 4        | 2,313,441 | 11,562    | **82.8%**               | 17.2%     |
| 5        | (beam)    | —         | 32.6% of top-6000       | —         |

The 4-phoneme row: only **0.5% of sequences** are real words, yet they hold **82.8% of the mass**.
English is not sparse in phoneme space — it is concentrated precisely where the probability is.

### ⚠️ But I over-read this, and the correction matters more than the finding

"97.9% of the mass is claimed" is true and **does not mean there's no room.** It means the
*highest-probability* short strings are taken. An independent measurement of the operationally
relevant question — take 300k **phonotactically plausible** generated pseudowords, how many are
already real English (vs SCOWL95 ∪ ESDB2026)?

| length | already real English | also real in es/it/de/nl/pt/fr |
|--------|---------------------|-------------------------------|
| 3      | **77.2%**           | 13.93% |
| 4      | **50.6%**           | 12.82% |
| 5      | 22.4%               | 4.30%  |
| 6      | 1.6%                | 0.68%  |
| 7      | 0.2%                | 0.08%  |
| 8+     | ~0.0%               | ~0.01% |

At length 4, **half** of plausible candidates are free — re-roll and you find one. Not 2%. The
two measures answer different questions (mass is dominated by the best candidates; this counts
all plausible ones equally), and **this one is the one that governs a rejection sampler.**

**And it composes with the objective error above into a single mistake.** If model logprob explains
only ~16–30% of wordlikeness, then "the high-logprob region is taken" barely matters — those
weren't the words we should have been selecting anyway. My mass-pessimism and my logprob-ranking
were the *same* error: treating model probability as the thing that matters. Correcting one
corrects both, and the project gets **more** viable, not less.

**Operational rule:** at **≥7 characters both the real-word and foreign-collision checks are
nearly moot**; at **≤5 they are mandatory**. Spend the filtering budget at the short end only.

### Two data bugs in the spikes above
- **The training lexicon is Webster's Second International, 1934.** `/usr/share/dict/web2` is
  missing `internet, email, blog, website, online, app, laptop, download, wifi, podcast, selfie,
  emoji, google, teenager` while retaining `zyzzogeton` and `quaquaversal`. So `wordfreq ∩ web2`
  is **systematically biased toward archaisms** — which plausibly explains the Latinate flavor of
  the debris (`exagger`, `disting`, `sential`). I called this "acceptable for learning word shape."
  It isn't.
- **Spike 4 destroyed the schwa distinction.** CMUdict has **no separate schwa symbol** — it
  encodes it in the stress digit: `AH0` = /ə/, `AH1`/`AH2` = /ʌ/ (clincher: `above → AH0 B AH1 V`;
  same for `ER0`/`ER1`). Spike 4 strips stress digits, so it collapsed them. `payshun` should be
  /peɪʃən/, `tubul` /təbəl/. Doesn't change the debris conclusion, but the model was wrong — and
  **the schwa instinct in the original plan was better-founded than I credited**: schwa is
  *lexically* real and stress-encoded, not merely a realization-level effect.

### The real-word check, sized correctly
`SCOWL95 ∪ wordfreq-en` = **805,256 words** (my "~500k" was low; the spikes' web2 ∪ wordfreq-300k
= 442,587 under-prunes by ~half). Marginal contributions: SCOWL95 adds 378,231 unique;
wordfreq-en adds 159,362; **ENABLE adds 168** — it's essentially a SCOWL subset, take it only for
public-domain purity. Ships as **1.45 MB as a bloom filter @0.1% FP** — trivially browser-sized.
Covers `yeet/rizz/sus/london/google/children`; misses `cromulent/doomscroll` (→ kaikki).
⚠️ **SCOWL v1 was deprecated 2026-02-17**; successor ESDB is self-described alpha with no official
release. For foreign collisions: **wordfreq thresholded at `zipf > 2.0` across 42 languages** —
not Wiktionary/kaikki, because wordfreq has *frequencies* and binary membership over 8.9M words
rejects obscure entries no speaker would recognize.

## The central problem: logprob-ranking selects morphological debris

I originally thought sampling was the bottleneck and enumeration would fix short words. It
isn't. Enumerating all 456,976 4-letter strings and taking the top by logprob gives:

> sque, ency, aque, mism, prer, bism, rity, guer, ungo, lign, loat, cacy, lism, vity, alve, epit, aphy

Beam search at length 7 gives:

> disting, conting, interly, sociate, marging, athless, exagger, multing, flation, viction, intered

These are English **suffixes and truncations**, not words. And it's structural, not a bug:

- **Optimizing surface English-likeness drives you onto the real-word manifold.** The
  highest-probability strings *are* English words — at length 5, only **249 of the top 4,000**
  by logprob survive real-word pruning (93.8% are real).
- **So the nearest non-real points to that manifold are fragments and near-misses.** Once you
  delete the real words, what remains at the top of the ranking is precisely the stuff that is
  English-shaped but incoherent — because coherent English-shaped strings already *are* English.

A character n-gram has no notion that a word needs a **stem**. It cannot help producing
`exagger`.

### The debris is MORPHOLOGICAL, not phonological — and phonology does not fix it

I claimed the fix was phonology, on the theory that "phonology gives you the syllable, and
syllable well-formedness separates a word from a fragment." **Tested it. Wrong.**

The most phonotactically probable non-words, exact enumeration over the phoneme space:

- **3 phonemes**: `uns, unt, bul, iks, stee, ust, unee, vul, reet, ful, lus, int`
- **4 phonemes**: `reeul, ekst, unsee, stree, unree, ublee, unlee, dist, unul, ubul, iklee, inst`
- **5 phonemes**: `kunsee, subul, sublee, insing, rizum, ilitee, payshun, uniks, tubul, dister, imping, riklee, prusee, mutiv, diklee, anting, vizum, sizum, loosiv`

Identical debris, just in IPA: `ʌn-` (un-), `-li` (-ly), `-ɪŋ` (-ing), `-ʃʌn` (**`payshun`
is literally just "-tion"**), `-ɪlɪti` (`ilitee` = "-ility"), `-ɪzʌm` (`rizum`/`vizum`/`sizum`
= "-ism"), `-ɪv` (`mutiv`/`loosiv` = "-ive"), `-ʌbʌl` (`ubul`/`tubul`/`subul` = "-able").

So the two things I had conflated:

- **Phonology buys pronounceability.** `vizum`, `loosiv`, `prusee`, `kunsee`, `bul`, `reet`
  are all sayable, unlike orthographic `ency`, `aphy`, `sque`. Real gain — keep it.
- **Phonology does not buy coherence.** Morphological debris is not a phonological
  phenomenon, so no surface phonological model can exclude it.

**The mechanism, now clear:** the training set is full of derived forms, so the model learns
`-tion`/`-ity`/`-ism`/`-able` are very high probability endings. Every *specific* real word
using them is already taken. So the free mass necessarily concentrates on novel recombinations
of those same affixes — i.e. affixes standing alone. `payshun` is that process in one word.

**The prediction this made**: train on **stems only** — strip derivational morphology, keeping `X`
only where `X` is itself a word — and the debris should vanish, because the model never learns
`-tion` as an ending at all.

### ❌ TESTED (spike 5). The prediction did NOT hold — and the reason is the real finding

Controlled A/B, identical data and model and beam, only stems-vs-full-words changed. The debris
barely moved:

| length | FULL WORDS | STEMS ONLY |
|--------|-----------|-----------|
| 7 | `disting, conting, sociate, exagger, flation, plation` | `flation, conting, extrate, plation, socious, contral` |
| 8 | `stration, praction, oversion, dictable, spective` | `stration, sciation, spection, praction, erration, punction` |

**Why: English has two derivational strata, and the heuristic can only reach one of them.**

- **Germanic / productive**: `happy→happiness`, `run→running`, `dark→darkness`. Concatenative, and
  **the stem is a free word**. "Strip if the remainder is a word" handles these — it decomposed
  33.4% of the lexicon.
- **Latinate / bound**: `station`, `creation`, `inspection`, `construction`, `receive`, `permit`,
  `transfer`. **The stems are bound morphemes** — `spect`, `struct`, `ceive`, `mit`, `fer`, `duce`
  are *not free words*. **No "is the remainder a word" test can ever touch these.**

**And the debris lives entirely in the Latinate stratum.** `stration`, `sciation`, `spection`,
`praction`, `flation`, `plation`, `payshun`, `ilitee`, `rizum`, `tubul` — all Latinate. So the
stripper removed exactly the morphology that *wasn't* causing the problem and left untouched the
morphology that was. Confirming detail: `creation` never decomposes, because reaching `create`
needs an `-ion` suffix *and* e-restoration, and `creat` isn't a word — so **every `-tion` word
stays in the "stem" inventory in force**, which is precisely why `-ation` debris survives.

**So the fix is not a better heuristic — it needs a morphological database that knows bound stems**:
CELEX, MorphoLex, or MorphyNet / UniMorph's derivational branch. That's a real dependency, not an
afternoon. (Note this is *not* what UniMorph's main data gives you — that's inflectional.)

⚠️ **The heuristic's failure mode was predicted by our own earlier result and I missed it.** v1 of
the stripper tested the remainder against web2 (235k words, 1934 unabridged) and produced folk
etymology: `international = tern + -ational + in-` (the seabird), `between = twee + be- + -en`,
`president = side + -ent + pre-`, `business = bus + -ness + -y`. Because only **33% of 3-letter
strings are free and *zero* 2-letter ones**, "is the remainder a word?" is almost always **yes**, so
greedy stripping runs to the bottom. A zipf≥3.0 frequency floor on the remainder killed the worst
(`tern`, `twee`, `side`) but not the rest: `recently = cent + re-`, `married = mar + -ed + -y`,
`department = part + -ment + de-`, `amazing = maze + -ing + a-`. **Latinate prefixes are the
residual problem** — `de-`/`re-`/`a-`/`im-` strip off words whose stems aren't productively derivable.

### Composition needs sandhi, and the rules are stress-conditioned
Naive concatenation gives `lique + -ashun = liqueashun`. Adding English's orthographic joins
(drop final `e` before a vowel-initial suffix, `y→i` before a consonant-initial one, double a final
consonant after CVC) fixes that → `liquashun`, but **over-applies**: `hered + -ashun = hereddashun`.
English's consonant-doubling rule is conditioned on **stress**, not on a CVC pattern — so sandhi
needs the stress information CMUdict has and spike 4 threw away. Another reason not to strip the
stress digits.

### What this means for sequencing
The morphology fix is a real project (morphological database + stress-aware sandhi), **not a v0
tweak**. Which is good news for sequencing: v0 should ship on the surface char model, debris and
all — the vocab-300 render already proves the debris doesn't kill the experience.

## Confirmed ship-blocker: profanity

On spike 2's **first run**, within the top 6,000 words: `diagnosis→masturbed`, and
`interrorist` (contains "terrorist"). A substring scan of 432k short non-words against 38
stems flagged 58 hits across 9 stems (`sement`, `whor`, `ueer`, `rror`, …). Note the risk
**grows with length** — more room to contain a bad substring — and the product lives in the
7–11 char band. Exact-match blocklisting is insufficient; needs substring matching over a
curated multi-language stem list, with care taken over false positives (`afag`).

## We have been optimizing the wrong objective

Every spike above ranks candidates by **model logprob**. The literature says that's at best a
third of the target, and the wrong third for our regime:

- **Phonotactic probability explains only ~30% of human wordlikeness** for CVC nonwords
  (Vitevitch 2025: human ratings vs V&L segment/biphone sums, r ≈ .55–.56, n=19 raters,
  60 items).
- **Neighborhood density beats it.** Bailey & Hahn (2001): Generalized Neighborhood model
  **R² = 20%** vs biphone transitional probability **R² = 16%**, the two overlapping at
  r = .531 — so each adds only ~3–6% unique variance. Their verdict: the lexicon dominates,
  phonotactics contributes little.
- **And the split is regime-dependent.** Frisch et al. (2000) find the stochastic grammar wins
  in the *low*-probability tail (grammar r ≈ .73 vs neighborhood r < .34) but the two **tie**
  for high-probability items (≈ .78 each). Our pseudowords sit in the high-wordlikeness region
  by construction, so **Bailey & Hahn's regime is ours: neighborhood density matters more than
  n-gram probability.** (These two papers genuinely conflict on effect size — Frisch R²≈.76 vs
  B&H R²≈.20 — most likely a stimulus-range artifact. Don't cite one without the other.)
- **Length has an independent penalty.** Frisch et al.: 2-syllable > 3-syllable > 4-syllable
  wordlikeness, p<.001, *over and above* the probability model's own length penalty. Our long
  pseudowords will feel less wordlike no matter how well we match n-grams.

**Implication:** the ranking key should be a neighborhood-density statistic (or a blend), not
logprob. Validate against the **UCI Phonotactic Calculator**
(https://phonotactics.socsci.uci.edu/about — 16 metrics, accepts custom corpora), not our own
model's score. Scoring candidates with the same model that generated them is circular anyway.

## Zipf's law of abbreviation is weak, and it saturates — which explains our own data

Piantadosi et al. (2011), BNC: length↔frequency Spearman **ρ = 0.121** — about **1.5% of
variance**. Information content does better (ρ ≈ 0.161–0.168, ~3%), and partialling out
information content kills the frequency effect entirely (ρ = −0.009, n.s.). This is a weak
tendency, not a law.

Crucially (their Fig. 2): the relationship **saturates** — low-probability words all have
roughly the same average length. **This independently explains spike 1's puzzling result** that
English length-by-frequency-decile was nearly flat (6.5 → 7.0 → 7.2 → … → 7.2). I noticed the
flatness and didn't know why. Now I do: it's real, it's expected, and only the top decile moves.

**Implication:** the length gradient is only needed in the **top few thousand ranks**. Across the
rare tail — exactly where the slider does its substituting — length is flat in frequency, so
length-stratification simplifies to per-word length matching plus special handling at the head.

## Prior art: this is Hu & Nation (2000), and it just failed to replicate

**Hu, M., & Nation, I.S.P. (2000).** *Reading in a Foreign Language* 13, 403–430. They replaced
low-frequency words in a fiction text with **nonsense words** to force 80/90/95/100% coverage,
and measured comprehension (n=66). 80% → nobody achieved adequate comprehension; 90% → small
minority; 95% → a few more, still a minority; 100% → most. Regression → the canonical **98%**
threshold.

**That is this project's slider, run as a lab experiment 25 years ago.** And:
**Kremmel, Indrarathne, Kormos & Suzuki (2023)**, *Language Learning* 73(4), 1127–1163,
doi:10.1111/lang.12622 — re-ran it with 104 Sri Lankan adult L2 learners in a non-WEIRD,
non-academic context and **did not replicate**: much less variance in reading scores explained
by coverage. (Read via abstract/secondary only — verify before building on it.)

So the honest framing is not novelty. It's that the canonical 98% figure rests on a regression
over **66 students**, it has now failed to replicate once, and this toy is a replication vehicle
pointed at a live open question with n ≫ 104.

### Existing generators do not save us
- **UniPseudo** (New et al. 2023, 64 languages, http://unipseudo.lexique.org/) — position-specific
  orthographic trigram Markov chain, generates from *your* wordlist, fixed length per run
  (a feature for us). **No morphology.**
- **Wuggy** (Keuleers & Brysbaert 2010) — onset/nucleus/coda subsyllabic bigram chain, concentric
  frequency search. Two problems: New et al. note it recombines subsyllabic elements from the
  whole lexicon and so **does not preserve word-class morphology** (our debris problem, again);
  and its default "match 2 of 3 segments" **derives each pseudoword from a specific real word by
  changing one subsyllabic slot** — which is precisely the documented English Lexicon Project
  failure (`addomen` from `abdomen` is recoverable, and pseudoword RTs get contaminated by base-word
  frequency; Perea et al. 2005, Yap et al. 2015). That is the source-similarity trap, by design.
  Also: PyPI (wuggy 1.1.2) and the master README contradict each other on distribution; license
  unresolved.

**Neither tool solves the morphology problem, and Wuggy actively violates source-independence.**
"Don't build a generator" is only half right — the off-the-shelf options are aimed at a different
target (matched stimuli for lexical decision) than ours (a coherent parallel lexicon).

### Coverage and comprehension decouple — so coverage % is the wrong slider variable
Laufer & Ravenhorst-Kalovski (2010), n=745, Table 3: 1,000→2,000 families buys the **largest**
coverage jump (+9.09%) but the **smallest** comprehension gain (+7 points); 5,000→7,000 buys only
**+1.3%** coverage but **+17 points**. Low-frequency words are often the key content words.
**A coverage-% slider systematically overstates how comprehensible the low settings are.**
Drive the slider from vocabulary size; display coverage *and* expected comprehension.

Model knowledge as **σ(a·(log f − b))**, slider moves **b**, expose **a** as learner sharpness —
and fit both against **Brysbaert et al. (2019) word prevalence norms** (62k English lemmas,
>220k participants: a measured P(know) per word) rather than inventing them. Steepness is
L1-dependent (cognates flatten it for Romance-L1 readers), which is a genuinely interesting knob.

Slider labels should use Nation's own calibration, which is far more visceral than percentages:
**95% coverage = 1 unknown word in 20 ≈ one per two lines of text; 98% = 1 in 50.**

## Profanity filtering: the obvious fix is structurally impossible

Verified live 2026-07-15. This is the confirmed ship-blocker, and the first three things you'd
reach for are all dead ends:

- **🔴 Any bag-of-words classifier cannot work — structurally, not incidentally.**
  `alt-profanity-check` (the only maintained one, v1.9.0, MIT, 2026-06-11) is `CountVectorizer` +
  `LinearSVC` trained on 200k *sentences*. **A novel pseudoword is out-of-vocabulary, so every
  feature is zero, so it predicts "clean" every time.** This applies to *any* BoW model. The whole
  PyPI filter category is useless for us. (`better-profanity` 2020, `profanity-check` 2019,
  `profanity-filter` 2020/GPL-3.0 — stale anyway.)
- **🔴 Perspective API is sunsetting** — "service is officially ending after 2026", active only
  until 2026-12-31, no migration support. Do not build on it.
- **🔴 HateBase is dead and the data is not recoverable.** Retired 2022, API deprecated before the
  site. Wayback captured only the JS shell — the `/vocabulary` snapshots contain **zero term data**.
  Every GitHub "mirror" is an API client, not a dataset. Even Davidson et al.'s repo, whose readme
  *describes* `hatebase_dict.csv`, **does not contain that file** — only `refined_ngram_dict.csv`
  (178 n-grams, **19 single-token**, MIT).

### The cost asymmetry inverts for us — and that simplifies the hard part
The moderation literature's central advice does **not** transfer:

- **Normal moderation:** a false positive **silences a real person** → favor precision. This is why
  Davidson et al. concluded "a smaller lexicon with higher precision is preferable to a larger
  lexicon with higher recall" (their HateBase false positives: *yellow, oreo, bird*).
- **This toy:** a false positive **discards one candidate from an infinite generator** — cost ≈ zero.
  A false negative means **the toy emits a slur**. → **favor recall, tune aggressively.** The
  HateBase false positives that ruined their classifier are nearly harmless to us.
- **Reclamation depends on speaker identity, which a generator categorically lacks.** So reclaimed
  terms get **blocked, not exempted** — and the context-dependence problem that dominates this
  literature largely evaporates. There is no speaker to silence.
- **Exact match is insufficient** — need edit-distance + phonetic (Soundex/Metaphone), since a
  generated string can land one character off a slur (cf. spike 2's `interrorist`). But
  leetspeak/homoglyph handling is **unnecessary**: we control generation.

### The permissively-licensed stack that actually works
- **Wikipedia's three lists via the MediaWiki API** (`action=parse&prop=wikitext` — works cleanly,
  no DBpedia or HTML parsing needed). CC BY-SA 4.0. Measured: *List of ethnic slurs* 602 rows →
  766 variants → **481 single-token**; *List of religious slurs* → **89**; *disability-related terms*
  → **64**. **~634 single-token total.** Extract bare terms only (facts), not the prose annotations.
  ⚠️ The disability list is mostly ordinary English (`Acoustic, Afflicted, Batty, Bonkers, Daft`) —
  including it wholesale would over-block badly. (`List_of_LGBT_slang_terms` is a redirect, not a list.)
- **LDNOOBW** — CC BY 4.0 ✅, the real Shutterstock list. EN = **403** (279 single-token). Profanity,
  not slurs. Last commit 2020-07-13.
- **google-profanity-words** — MIT ✅, ~962 EN, actively maintained (v3.0.7, April 2026). ⚠️ **Not
  actually from Google** — no provenance evidence; its multilingual claim is fiction (French ~23).

### Skip these
- **The Weaponized Word** — best-scoped by far (10,555 terms / 137 languages, official HateBase
  successor, same team) but **its ToS forbids redistribution**. Blocked.
- **HurtLex** — CC BY-**NC**-SA 4.0 (NonCommercial; stated only in README prose, no LICENSE file,
  GitHub API reports `license: None`). And the quality is worse than its labels: **all 53 languages
  are v1.x — none has ever been hand-corrected** (the repo's own convention reserves `2.0` for the
  first manual correction; no `2.x` exists for any language). Built by BabelNet sense-expansion from
  1,072 curated Italian lemmas → 8,228 English rows, an ~8× inflation. The slur-relevant slice
  (`ps` + conservative + single-token) is **133 lemmas** and includes `barbarian, boob, boor,
  changeling`. `QAS` is pure noise (`abidance, accustomed, acolyte, agrarian`). Only worth it if NC
  is acceptable and you hand-prune.
- Every post corpus (Gab Hate Corpus, Stormfront, MLMA, Multilingual HateCheck) — labeled
  *sentences*, useless for single words.

## Trademark screening: don't build it — and the reason is legal, not logistical

Verified live 2026-07-15. **There is no free, bulk, machine-readable, legally-redistributable
trademark corpus outside the US.** Every major register is now account-gated, contract-gated,
or priced:

- **EUIPO bulk open data is dead.** The `open-data` portal 301s to the homepage; deep links
  soft-404; `opendata./data./bulk.euipo.europa.eu` are NXDOMAIN. Wayback's last successful
  capture is **2022-12-22**. The four `data.europa.eu` records are a zombie catalogue — CC-BY-4.0
  licensed (the only clean licence found anywhere here) and attached to files that 307 to an HTML
  error page. Last modified 2020-01-21.
- **WIPO**: the Madrid Monitor anonymous FTP (`ftpird.wipo.int/wipo/madrid/romarin/`) carries a
  rolling ~6 months of **daily deltas with no baseline** — because it exists as the update channel
  for **CHF 30,000** full-database licensees, not as an open dataset. Global Brand Database terms
  forbid automated queries, bulk download, and scraping outright; the FAQ explains why ("our
  agreements with the national offices ... preclude us from redistributing data").
- **TMview** (136M marks, 80 countries) is consultation-only. It has an undocumented,
  unauthenticated internal API (`POST tmdn.org/tmview/api/search/results` returns results with no
  key) — **and it is not licensed for this.**

**The clause that settles it.** EUIPO's legal notices carry an explicit TDM opt-out (with a
machine-readable `<TDM-RESERVATION: 1>` marker) reserving against "text or data mining, web
scraping or similar reproductions ... for whatever purpose **other than scientific research**",
invoking Art. 4(3) of Directive (EU) 2019/790, plus: "**The extraction of substantial parts of
EUIPO databases ... is forbidden.**" TMview/EUIPN carries the identical clause. Note that
`euipo.europa.eu/robots.txt` only disallows `/user-area/`, and `tmdn.org/robots.txt` explicitly
`Allow: /tmview/*` — **robots.txt permissiveness is not a licence.** A public web toy is outside
the permitted purpose.

### The decisive argument: there is no question to answer
The data problem above is real but it's a distraction. **String-only screening of an invented word
is close to meaningless, and class-code matching is legally incoherent:**

- [USPTO](https://www.uspto.gov/trademarks/search/likelihood-confusion): confusion requires
  similarity **and** that "the goods and services are related" — "This is how identical trademarks
  with different owners can be registered for Dove soap and Dove ice cream bars, or Delta faucets
  and Delta air transportation services." You get rights to a word only *as used with specific
  goods or services*.
- **TMEP §1207.01(d)(v)**: "**The classification of goods and services has no bearing on the
  question of likelihood of confusion**" — what controls is how the goods/services are *identified*.

So all three naive designs fail: string-only (identical marks lawfully coexist), class-code matching
(legally incoherent), and ML-on-the-string (no goods/services signal). What actually controls is
semantic comparison of goods/services text — which is why Namelix's screen takes *business context*
(probed live: `Delta`+`airline` → **risky**; `Delta`+`artisanal sourdough bakery` → **clear**), and
why every vendor including Corsearch/CompuMark still disclaims legal advice. **Nobody sells
clearance; they all sell triage.**

**A pseudoword has no goods or services, so there is no likelihood-of-confusion question to answer.**
Don't build trademark screening. Disclaim it — which is exactly what GoDaddy, Shopify, and Brandroot
do (GoDaddy's registration agreement §8 shifts the entire warranty to the user; ICANN UDRP ¶2:
"It is your responsibility to determine whether your domain name registration infringes...").

### The two residual gestures worth making
1. **A small famous-marks screen for exact/near-exact hits**, on embarrassment grounds rather than
   legal ones. **Wikidata brands via SPARQL** is the only genuinely redistributable source found:
   `query.wikidata.org/sparql`, no key, **CC0** (database rights waived, no attribution required),
   measured **39,625** brand items (`?b wdt:P31/wdt:P279* wd:Q431289`).
2. **WIPO 6ter** — `ftp://ftpird.wipo.int/wipo/6ter/6ter.zip`, 447 MB, anonymous FTP, updated
   2026-05-01. **The one genuine catch in this whole area**, because it's a *different legal regime*:
   6ter protects state emblems and **IGO names and abbreviations** outright, with no
   goods/services test — so a generator emitting English-like strings landing on `UNESCO`/`NATO`-shaped
   forms is a real and distinct hazard, and it's the only such hazard with real bulk data.

WIPO keeps **no Art. 6bis famous-marks list** (confirmed) — 6ter is what gets confused with it, and
it isn't trademarks. INTA keeps no list either, only recommended policies.

⚠️ **Unresolved conflict between two independent research passes on India's well-known marks list.**
One measured `tmrsearch.ipindia.gov.in/tmrpublicsearch/docs/List_of_Well-Known_Trade_Marks_as_of_10.02.2025.pdf`
at **exactly 345 entries**, 2,283,373 bytes, Last-Modified 2025-11-14. The other reports
`ipindia.gov.in/trade-marks-publications-list-of-well-known-trade-marks` at **~900–1,000 marks**,
2.18 MB, updated 2026-07-13 (extraction lossy, count unverified) — while the first pass found that
host timed out or NXDOMAIN'd. Different hosts, possibly different vintages. **Do not cite a count
for this until someone re-fetches both.** Moot anyway if we don't build the screen.

**Not legal advice** — a reading of published terms.

## Tooling verdicts (verified July 2026)

### Hand-rolling the n-gram was right — and for the reason that matters
- **kenlm is structurally wrong for character data, not just inconvenient.** Modified Kneser-Ney
  estimates discounts in closed form from counts of n-grams seen exactly 1/2/3 times. With a
  ~30-symbol alphabet there are **no singleton unigrams** → `n1 = 0` → the discount estimate goes
  negative → `BadDiscountException: 1-gram discount out of range`. Issue
  [kpu/kenlm#290](https://github.com/kpu/kenlm/issues/290) *is* this exact use case.
  **More data makes it worse.** `--discount_fallback` is disowned upstream and means you've
  silently abandoned modified KN anyway. Also LGPL-2.1. (It *is* on PyPI now — `kenlm` 0.3.0,
  2025-04-07, sdist only, needs CMake — the "GitHub-zip only" folklore is stale.)
- **Witten-Bell cannot break**: λ = T/(T+N), both direct counts, **no discount estimator to fail.**
  The choice in these spikes was correct for the decisive reason, by luck.
- **`nltk.lm` is unusable at runtime**: `KneserNeyInterpolated(discount=0.1)` default vs the
  literature's 0.75 (silently under-discounted); and `_continuation_counts` linear-scans every
  distinct n-gram of the next order on **every** `score()` call — a 100–1000× perf defect,
  [nltk#2495](https://github.com/nltk/nltk/issues/2495), **open since 2020-02-04**.
  **Use it as a test oracle, not a runtime**: assert agreement to ~1e-9 on a few thousand words,
  ship ours.

### Fuzzy lookup: hand-roll symmetric-delete, and ED1 needs no index at all
- **ED1 → build nothing.** A `set` + ~450 Norvig variants/query ≈ 100–150 µs. `rapidfuzz` brute
  force is ~65 ms — **the dumb approach is ~500× faster.** Stop here if ED1 suffices.
- **ED2 → symmetric-delete** (9→37 probes, vs query-side generation's ~25k–60k). But **don't use
  `symspellpy`** at 805k: its index is literally `dict[str, list[str]]` → ~19.4M keys ≈ **4–6 GB**.
  Keep the algorithm, drop the container — 64-bit hashes of delete keys in a sorted
  `numpy.uint64` array (**155 MB**, ~30× shrink), all 37 probes batched into one vectorized
  `np.searchsorted` → ~3–10 µs. Front with a bloom filter (~23 MB @1% FPR) — and since we score
  *invented* strings, the answer is overwhelmingly "no", and symmetric-delete has **no false
  negatives**, so all-probes-miss is a *provable* NO exiting in ~1 µs. ~50–60 lines.
- ⚠️ **License trap:** `import Levenshtein` is **GPL-2.0+**; `from rapidfuzz.distance import
  Levenshtein` is **MIT**. Same org, same algorithm. Also `symspellpy` **6.10.0 (2026-07-11)**
  silently changed the default to pure-Python `DAMERAU_OSA` — needs `symspellpy[editdistpy]`;
  README still documents the old behavior.

### G2P / P2G
- **`g2p_en`** — Apache-2.0, self-contained (bundles its LSTM), **handles arbitrary non-words**,
  works on 3.13. Stale (2019) but working. **This is the permissive escape hatch.**
- ⚠️ **`phonemizer` AND `espeak-ng` are both GPL-3.0.** Fine server-side; **not if we ship espeak
  to the browser via WASM for the audio feature.** Use `phonemizer-fork` + `espeakng-loader`
  (bundles espeak-ng 1.52, no system install) if GPL is acceptable.
- ⚠️ **espeak silently falls back to English for non-words in other languages.** With
  `language_switch='remove-flags'` you get English phonemes *labeled French, with no warning* — a
  silent correctness bug for "does this sound like a real French word". Use `remove-utterance`,
  which fails loudly.
- **P2G is solved by column-swapping any joint-sequence model.** Recommendation:
  **`yoyodyne`** (v0.5.24, 2026-07-06, **Apache-2.0**, actively maintained, same Kyle Gorman group
  as WikiPron) — small-vocabulary seq2seq built for exactly this, consumes TSVs, swap the columns
  → P2G. Sequitur also works but PyPI is broken (`AttributeError: 'SwigPyObject' object has no
  attribute 'thisown'`; fix merged 2025-10-20, **never released** — install git master + swig).
- **WikiPron** — word+IPA, **348 languages, 6.67M pairs**, IPA already space-segmented (ideal for
  alignment). `eng_latn_us_broad.tsv` = 100,932 entries. Apache code / **CC BY-SA 4.0 + GFDL** data.

### The joint grapheme-phoneme chunk model has a real toolchain cost
Pre-computed alignments exist — [ckw017/aligned-cmudict](https://github.com/ckw017/aligned-cmudict),
135,036 lines (⚠️ **no license file at all**). Top learned units: `e|r→ER0` 16,811, `n|g→NG` 6,977,
`s|h→SH` 3,479, `c|h→CH` 3,149, `t|h→TH` 2,771, `t|i→SH` 2,228, **`p|h→F` 1,165**. So `ph ↔ /f/`
is there — **but `tion ↔ /ʃən/` as one unit is NOT**, because `phonetisaurus-align` defaults to
`seq1_max=2, seq2_max=2` and the corpus was built with defaults (measured: grapheme chunks are
only size 1 and 2, **zero 3+**). Getting `tion` as one chunk needs `--seq1_max=4`, which needs
Phonetisaurus built against **OpenFst ≤1.7.x** — its issue #70 ("fails to build with openfst 1.8")
has been **open since 2021-10-10** while OpenFst is now 1.8.5. Options: use the 2/2 alignments and
let the chunk model compose them, or align with **MFA** (alive, PyPI 3.4.1, 2026-07-11, MIT) /
`pynini` (alive, wheels cp39–cp314).

### Profanity matching: substring over-blocks 5× more than ED1
Measured against real English (~275 single-token LDNOOBW terms):

| strategy | real English wrongly flagged |
|----------|----------------------------|
| exact | 0% (but zero evasion resistance) |
| **ED1** | **0.46%** |
| **substring** | **2.21%** |
| ED2 | 4.69% (unusable) |

Driven entirely by short terms: `ass` 1,391 (`bass, mass, class`) · `tit` 1,119 (`petit, title`) ·
`cum` 495 (`scum, accumulate`) · `anal` 218 (`banal, canal`) · `mong` 215 (`among, monger`) ·
`rape` 157 (`grape, drape, therapeutic`) · `semen` 72 (`basement`) · `smut` 62 (`bismuth`).
**So: don't substring-match the whole blocklist** — restrict substring/ED1 to a curated
high-severity subset, or `ass`/`tit`/`mong` shred legitimate output. `pyahocorasick` does the
substring pass at ~5M words/sec. Never substring-match the *real-word* check, where FPs are real.

- **Better data model than LDNOOBW: [`dsojevic/profanity-list`](https://github.com/dsojevic/profanity-list)**
  (MIT) — severity 1–4, per-entry **`allow_partial`**, explicit exceptions (`sp*` stops
  `arse`→`sparse`), and **tags** (`racial, religious, lgbtq, …`) so categories can be dropped
  wholesale. The tags matter: Dodge et al. 2021 (EMNLP) found only **31%** of LDNOOBW-blocked C4
  documents were "largely sexual", and AAE-aligned text was removed at **42%** vs WAE **6.2%** —
  the precision point transfers to us, the bias point largely doesn't (no author, no context), but
  it's the reason to prefer a tagged list. `obscenity` (npm, MIT, 2026-01-18) is the best
  off-the-shelf matcher — substrings + confusables + leetspeak — English-only, 70 patterns.
- **"Google's blocklist" is folklore.** It traces to a **2011 client-side JS scrape** of Google's
  defunct "What Do You Love?" microsite. `coffee-and-fun/google-profanity-words` is that scrape
  merged with LDNOOBW (contains 384/403 of `en`) — **CC-BY content relabeled MIT**, still claiming
  "banned by Google". Lineage proven by diffing the WDYL signature: `coffee-and-fun` 7/7,
  LDNOOBW 0/7.
- **Shutterstock's list *is* LDNOOBW** — one repo, `created_at 2012-03-09` at Shutterstock, later
  transferred; `shutterstock/List-of-…` 301-redirects there. Not a fork, not a second list.
- LDNOOBW reality check: **124/403 English entries (31%) are multi-word** and can never match a
  pseudoword → effective vocabulary **~275**. Non-English lists are wildly uneven (`de:66`,
  `da:20` containing English words, `tlh:3` — Klingon, first-class).

### Google Books Ngrams — answering the original plan directly
**It is WORD n-grams only, orders 1–5. There are no character n-grams in it.** You'd derive them
from the 1-gram list, which `wordfreq` already gives you in one `pip install`. Current version is
**v3 = `20200217`**; no v4 as of July 2026. ⚠️ **The documented line format is v2's, not v3's** —
v3 is one line per ngram with all years as comma-separated triples, and **POS tags are embedded in
the ngram field** (`_NUM`, `_NOUN`) — a parsing trap. English 1-grams alone = 24 shards,
**12.8 GiB compressed**; 5-grams = 19,423 shards (multi-TB). Only n-grams occurring >40 times are
included. CC BY 3.0. **Overkill; skip it.**

### wordfreq is frozen, not abandoned — and the freeze is a feature
PyPI **3.1.1 (2023-11-21)**; git tag **v3.2 (2025-01-04)** never published; repo not archived.
Reason, from Robyn Speer's SUNSET.md (Sept 2024), verbatim heading: **"Generative AI has polluted
the data"** — LLM-generated web text skews frequencies, and Twitter and Reddit both closed the
public data that were wordfreq's conversational sources. He endorses continued use; his argument is
that *updating* it would make it worse. **We want human word frequencies, so a pre-2022 snapshot is
exactly right.** English `large` = 321,180 entries; 42 languages. Alternatives: **SUBTLEX-US**
(74,286 words, 3.3 MB, CC-BY-SA, subtitle frequencies — better psycholinguistic realism);
**FineFreq** (arXiv 2512.09701, Dec 2025, CC BY 4.0) has **year-level** character frequencies for
1,900+ languages, so you can restrict to pre-2022 and dodge contamination deliberately — but it's
single-author and brand-new.

## ⚠️ The real project risk is licensing, not engineering

Nearly the whole data stack is **share-alike copyleft**:

| asset | data license |
|-------|-------------|
| Kaikki / Wiktextract (the best membership oracle) | **CC BY-SA + GFDL** |
| WikiPron (word+IPA, 348 langs) | **CC BY-SA 4.0 + GFDL** |
| UniMorph | ⚠️ **fragmented, and NC-contaminated — see below** |
| wordfreq **data** | **CC BY-SA 4.0** (code is Apache-2.0) |
| Wikipedia slur lists | **CC BY-SA 4.0** |
| aligned-cmudict | **no license at all** |

**The permissive path exists but is far narrower:** Wikidata Lexemes (**CC0** — 1,533,561 lexemes /
17,876,194 forms / 1,559 languages, but a brutal coverage cliff: only **2** languages have ≥100k
lexemes, 30 have ≥10k, **1,408 have <100**) + ICU `brkitr` dictionaries (Unicode-3.0; cjdict
315,964 / thaidict 26,383 — only 5 space-less-script languages) + SCOWL + the ~14 of 92 permissive
hunspell dictionaries.

⚠️ **Unresolved conflict between two research passes on SCOWL.** One recommends **SCOWL95** as half
of the 805k real-word union. The other reports that **size >80 triggers UKACD's verbatim-notice
obligation — "stay ≤80."** If that's right, the 805k figure carries a license string the other pass
didn't flag. Resolve before shipping the bloom filter.

**The genuinely unsettled question** — and I'm flagging it rather than pretending to answer it: is a
lexicon *generated* by a model trained on CC-BY-SA data a "derived database" that share-alike
attaches to? Nobody knows. For a free public toy this is probably moot (share-aliking the lexicon is
something you'd want anyway). It becomes real if this is ever commercialized. **Not legal advice.**

### Partial escape: Leipzig's *downloads* are CC BY, not CC BY-NC
The Leipzig Corpora Collection is two-tier, and the tier that matters is the permissive one. Verbatim
from `wortschatz.uni-leipzig.de/en/usage`: the project's data/applications/web services are **CC BY-NC**,
but "**The text corpora offered for download are made available under the Creative Commons licence
CC BY**" (German page confirms identically). And it ships **ready-made per-language word-frequency
lists** (`*-words.txt`: `Word_ID  Word  Frequency`) across **~270 downloadable languages** — the exact
primitive the foreign-collision check wants, attribution-only, no share-alike. Direct download
(`downloads.wortschatz-leipzig.de/corpora/<iso639-3>_<source>_<year>_<size>.tar.gz`) is not
bot-gated. Newest data 2024, built 2025-01-18; actively maintained.

⚠️ **But note the internal contradiction**: paragraph 1 of the same page says commercial use is
prohibited, paragraph 2 carves the downloads out as CC BY. The specific provision should govern, but
this is exactly the ambiguity to get confirmed in writing before shipping commercially — and they
explicitly invite contact.

⚠️ **And the lists are raw, not curated.** Measured on `eng_news_2024_1M` (648,809 entries): **29%
contain a space** (n-grams like `on the`, `due to`), **32%** carry digits/punctuation/diacritics
(`Gov.`, `won't`, `control”`), leaving **254,825** pure-letter single tokens — **130,607 at freq≥2**.
Frequency-1 is where the junk lives (`controlledwhether` is a real entry). So for *English* it is
**worse than `SCOWL ∪ wordfreq-en` (805k)**; its value is purely the multilingual tail, which itself
thins hard (English ~130k forms → Wolof ~18k). Format inconsistency to handle: docs say
`*_words.txt`, archives ship `*-words.txt`, and `wol_community_2017` has **4 columns and no
`meta.txt`** vs the documented 3.

**Net:** this widens the permissive path for the multilingual check specifically — but since that
check is a 0.04% filter that `wordfreq` already covers in one `pip install`, it changes nothing
material today. Recorded so the option is known if the share-alike question ever turns hostile.
(OPUS: **rejected** — grants no license at all, explicit ownership disclaimer plus notice-and-takedown,
and its largest component (26%) is unlicensed scraped subtitles. UDHR: **rejected categorically** —
English UDHR has **522 unique word forms**, ~0.4% of what's needed; it would call `banana`,
`computer`, and `dog` non-words. The Unicode project was delisted January 2024 and all official URLs
404. It's an encoding smoke test, not a lexicon.)

## The membership oracle: use two, in two places

Empirically validated, and the contrast is stark:
- **Kaikki correctly rejects `flurb`** (404, no page) and correctly accepts `saxophone`, `cinnamon`,
  `turnip`, `accordion`, `petrichor`.
- **hermitdave/FrequencyWords accepts `flurb`** — a textbook pseudoword is *in its English list*,
  along with `teh`, `becuase`, `definately`, `zampallo`. 54% of `en_full` is frequency-1 junk;
  casing is destroyed (0 uppercase lines — German `Freund`/`Haus` absent); clitics are split into
  `'s`/`'t`; and `en_50k` rejects `flurb` **but also rejects** `quixotic`, `petrichor`, `obfuscate`.
  Neither variant works. **Ruled out.** (Also: `archived: false` and `license: MIT` are both
  actively misleading — the wordlists are CC-BY-SA per the README, and
  [issue #19](https://github.com/hermitdave/FrequencyWords/issues/19) disputing the license has sat
  unanswered since 2021.)

**So: two checks in two places.** Kaikki (457 languages, 1,380,567 English forms, 2.84 GB gz /
23 GB raw, refreshed weekly) as the **generation-time** prune, offline where size doesn't matter.
`SCOWL ∪ wordfreq-en` (805k → **1.45 MB bloom**) as the **runtime** check that ships to the browser.
⚠️ Kaikki filters that are mandatory: drop `.forms` metadata junk (`table-tags`,
`inflection-template`), drop `romanization` entries, and drop `misspelling`/`alt-of` tags —
Wiktionary *documents* misspellings but tags them, so they're filterable. Per-language downloads are
**deprecated and will be removed**; process the raw dump. PyPI `wiktextract` is **1.99.7 from
2022-06-20** — install from git.

**web2 is dangerous, now confirmed by two independent passes.** The second put it best: it errs in
the **worst direction** — it would ship *real words as invented*. Three of the four spikes above
use it. Also: **use hunspell `lookup` rather than expanding** `.dic` — 82% of English stems carry
affix flags, `COMPOUNDRULE`/`ONLYINCOMPOUND` make surface forms rule-defined and unbounded, and
`unmunch` is deprecated and parses zero `COMPOUND*` directives so it *cannot* correctly expand
English. Lookup also errs toward "real word" — the safe direction here.

## UniMorph helps the morphology experiment, but does not solve it

`lemma⇥form⇥features` for 187 languages. English: **652,477 entries → 579,293 distinct forms /
399,575 lemmas** (also `fin` 2,737,048, `spa` 1,196,245, `tur` 570,420). That's a ready-made
lemma↔form mapping for the stems-only test.

**But note the mismatch:** UniMorph is **inflectional** morphology (`run`→`ran`). The debris
problem is **derivational** (`-tion`, `-ity`, `-ism`, `-able`). So UniMorph gives us the inflectional
half for free and **nothing** for the half that actually causes `payshun`. The derivational analysis
still needs Morfessor or the greedy strip-if-the-remainder-is-a-word heuristic.

⚠️ **UniMorph's licensing is worse than a first pass suggested — and it's dormant.** GitHub detects
**no license for 193 of 197 repos**; `unimorph/eng` has no LICENSE file. Scanning all 187 language
READMEs: 142 → CC BY-SA 3.0, **20 → no license anywhere**, **14 have no README at all** (including
`lat`, which carries 124 MB of data). **Hard NC blockers: `slk` is entirely CC BY-NC-SA 4.0** (and
it's the single largest data file, 78.8 MB); **`ces` and `ukr` are mixed** — the plain file is
CC BY-SA 3.0 but the bulk `.xz` is CC BY-NC-SA 4.0, so take only the plain file. Also **7 repos are
empty** (`epo grn mon oss pib pnb pqm` — Esperanto and Mongolian have nothing), and `fin` has no
`fin` file (split `fin.1`/`fin.2`). Dormant, not archived: `pushed_at` peaks in 2022–23 then
collapses (2025 → 2, 2026 → 3); `unimorph/eng` last commit **2023-02-16**; the master
`unimorph/unimorph` repo last commit **2019-10-19**.

⚠️ **And Wikidata Lexemes cannot carry English.** Its CC0 license is the best available, but
**English has only 151,482 forms / 74,063 lexemes** — **4× smaller than UniMorph `eng` (579,293)**
and half of DBnary's English. The strong languages are elsewhere (et 2.8M, de 2.0M, ar 1.8M forms).
So the CC0 backbone is a supplement for English, not a source. (Upside: there's a dedicated
lexemes-only dump — `latest-lexemes.json.bz2`, **416 MB**, refreshed every 2–3 days — no need to
touch the 100 GB+ full Wikidata dump.)

**Scope note: this area is over-researched relative to its importance.** The foreign-collision check
is a second-order filter — measured above at **0.04%** cross-language collision overall, and
**~0.1% at ≥7 characters**. `wordfreq` thresholded at `zipf > 2.0` across its 42 languages is one
`pip install` and is entirely adequate. Kaikki/UniMorph/DBnary/Wikidata-Lexemes only matter if the
project ever needs breadth beyond 42 languages, which it currently doesn't. Recorded here so nobody
re-runs it. (For the record: DBnary has inflected forms for **only 6 languages** — the other 21
editions ship ~460-byte stubs, and Spanish has *no* forms despite 120,724 lexical entries; kaikki is
**457** languages, and the "over 2,000 languages" figure floating around is unverified — don't cite
it; kaikki's `forms[]` is **18.8%** template junk that must be filtered.)

**One methodological trap worth keeping.** Counting distinct forms with
`cut -f2 | sort -u | grep -c .` under a UTF-8 locale **silently and catastrophically under-counts
non-Latin scripts** — a first pass got **188** unique Russian forms against a true **353,004**, and
**16** for Japanese against **10,848**. Two causes: `grep -c .` mishandles multibyte, and UTF-8
`sort -u` collates distinct strings as equal. **Always `export LC_ALL=C` and use `wc -l`.** This bit
our own spikes' neighbours: an apparent "438 duplicate entries" finding elsewhere was purely a
`sort` collation artifact.

## Open, unresolved

- The long tail is unhandled. In the render above, `universally` and `neighbourhood` never
  substitute at *any* slider setting because only the top 6,000 words were mapped — the
  rarest words, which most need replacing, fall through. You cannot enumerate the tail. This
  is an independent argument for composing morphologically rather than enumerating.
- Short function words: no same-length room, and the length-3 survivors are y/z/x junk
  (`oze, aky, eyr, pyk, ovu`). Unsolved by the char approach.
