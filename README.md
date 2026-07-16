# English-ish

An alternate vocabulary as close to English as possible without being English, plus a
comprehensibility slider: set how many words you know, and read a paragraph the way you'd read a
language you half-know.

At "you know the top 800 lemmas" (~80% token coverage):

> It is a **odome ferritorial confabulousby**, that a single man in **regelative** of a good
> **noisies**, must be in want of a **urant**. However little known the feelings or views of such
> a man may be on his first entering a **collapaloozas**, this **odome** is so well **geishby** in
> the minds of the **chromatsye solicity**, that he is **superating** the **megassed** property of
> some one or other of their **postmoded**.

80% coverage sounds survivable. It isn't. That's the point.

## Run it

    uv run python -m englishish.build          # rebuild public/lexicon.json (~40s)
    uv run python -m englishish.passages       # rebuild public/passages/ from 46 Gutenberg books
    uv run python -m englishish.render         # the map + mirrored irregularity
    uv run python -m englishish.check_letters  # letter-frequency check
    uv run python -m englishish.demo_nonfinite # non-finite forms English lacks

The site is `public/` — static, no build step. `python3 -m http.server 8731 --directory public`.
`data/` holds cached downloads (gitignored); see `data.py` for provenance. Builds are deterministic.

Every page load shows a random passage from 2,600 public-domain paragraphs across 46 Gutenberg
books, picked for register spread rather than popularity. That's the interesting axis: at a fixed
2,000-word vocabulary, coverage runs ~86% for children's books and ~78% for essays. Nation measured
the same thing (~88% novels vs ~83% newspapers) — the same vocabulary is a different language
depending on what you point it at.

The corpus is sharded because the page renders exactly one passage: shipping all 2,600 would cost
~500KB gzipped to use ~0.2KB. A random shard is ~20KB, and random-shard + random-passage-within is
still uniform over the corpus. First load is ~721KB gzipped, nearly all of it the lexicon.

## How it works

A type-weighted order-6 Witten-Bell character n-gram over SCOWL 70 (127k modern curated English
words, proper names excluded) generates candidates — the short end enumerated exhaustively, the
long end sampled. English lemmas are ranked by summed-form frequency, so `mouse` carries `mice`'s
frequency too. Candidates then have to survive a filter: not already English, not a recognisably
foreign word, pronounceable, not on a slur/profanity blocklist (checked on composed forms, since
affixation manufactures new strings), not recoverable from the word it replaces, and at least as
English-like as a real English word of the same length. Survivors are assigned length-stratified
and monotone within each bucket, every inflected form gets realized, and the result is
`public/lexicon.json`: `english_wordform -> [englishish_wordform, lemma_rank]`.

`lexicon.json` is the artifact boundary. Everything upstream can be swapped — a joint
grapheme-phoneme model, or a lexicon evolved from English by sound change — without the site
knowing.

### Morphology is mirrored, not regularized

English's irregulars aren't random. `sing/sang/sung`, `ring/rang/rung` and `swim/swam/swum` share
one alternation because they're the residue of Proto-Germanic ablaut. So the mirror works on
classes, not words: each English class gets one English-ish alternation applied to the same
members. English-ish has ablaut, i-umlaut, zero-marked pasts, suppletion and Latinate plurals in
the same places English does, which means an English-ish learner carries the same
learn-the-exceptions burden a real L2 reader does.

Paradigms are validated to collapse exactly where English's collapse: `walk/walked/walked` merges
past and participle, `sing/sang/sung` doesn't. Requiring all forms to be distinct would
over-differentiate every regular verb.

## Known limits

Measured, not guessed. Numbers in FINDINGS.md.

- **Latinate affix debris in stems** (`bring→ingly` — things that read like `-tion` wearing a hat).
  The big one, and not heuristically fixable: English's Latinate stems are bound (`spect`,
  `struct`, `ceive` aren't words), so no "strip it if the remainder is a word" rule reaches them.
  Needs CELEX / MorphoLex / MorphyNet.
- **Ranked by model logprob**, which explains only ~16–30% of human wordlikeness. Neighborhood
  density is the better key. Touches one function.
- **Homographs collapse** to the highest-frequency lemma (`saw` = see.PST or the tool). Needs a
  POS tagger — which is only needed for that and for lemmatization, because POS-appropriateness
  comes free from mirroring the affixes (`-tion` makes nouns, so its counterpart does too).
- **No consonant doubling** in sandhi. English's rule is stress-conditioned and generated stems
  have no stress, so applying it by CVC pattern gives `hereddashun`. Omitted rather than
  misapplied.
- **We under-use w/j/k/f** (0.47–0.76× English). The naturalness floor over-corrects: words
  carrying those letters score lower and get cut. Argues for targeting the letter distribution
  directly instead of through a logprob proxy.
- **No semantic drift**, so no false friends, so it's transparent rather than treacherous. This is
  what would make it actually hard.
- UniMorph gaps: `be` absent entirely, `child` has no plural, `find` has no verb forms. The
  irregular core is curated instead — safe, because irregularity is preserved by frequency.

## The lesson that cost the most

**Existence proves nothing.** Any categorical "is X attested?" test against a large word list
returns true almost always, because these lists have huge junky tails. Five instances, all the
same shape:

| test | what the junk did |
|---|---|
| "is the remainder a word?" (derivational stripper) | `international = tern + -ational + in-` — *tern*, the seabird |
| "is this consonant cluster attested?" | `mzee` legalized `mz-`, so `it → mze`; the abbreviation `hdqrs` legalized `hd-`, so `dog → hdy` |
| "≥12 attesting types?" | bare `q-` scraped 14, all loanwords, inflated by inflection — so `in → qir` |
| "is this an English word?" via wordfreq | claimed 100% of the 2-letter space — zero bits — producing a false impossibility that got designed around for days |
| "is this a word in language L?" via wordfreq, ×41 | called `eb` a word in nine languages, killing the rest of the 2-letter pool |

The fix is always the same: require frequency-weighted evidence, not existence, and make sure the
oracle answers the question you're actually asking. wordfreq answers "does this occur in text?";
only a dictionary answers "is this a word?". Using the first for the second is how a measurement
starts reporting impossibilities.

## Prior art

This slider is Hu & Nation (2000) — they replaced low-frequency words with nonsense to force
80/90/95/100% coverage and measured comprehension, on 66 students. That's where the canonical "98%
coverage needed" figure comes from, and Kremmel et al. (2023) failed to replicate it with 104 Sri
Lankan learners. So the honest framing isn't novelty; it's a replication vehicle for a
load-bearing finding that's currently wobbling, at n far greater than 104.

UniPseudo (New et al. 2023) is the closest existing generator and isn't a library — it's a 550-line
R Shiny app whose core is documented as "chaining trigrams or bigrams" over same-length models.
That's what `ngram.py` already does, at higher order with principled smoothing. Wuggy is
unsuitable by default: it derives each pseudoword from a specific real word by changing one
subsyllabic slot, which is the documented English Lexicon Project failure where `addomen` stays
recoverable from `abdomen`.

The old TODO in here said: Google 1-grams, trie dictionary, character-level Markov model. Two of
three are done. The first was a trap — Google Books Ngrams is word n-grams only, there are no
character n-grams in it, English 1-grams alone are 12.8 GiB, and the v3 line format isn't what the
docs describe. `wordfreq` is one pip install and gives you the same thing.

## Next

1. Fix the debris — wire a derivational database that knows bound stems.
2. Swap the ranking key to neighborhood density; validate against the UCI Phonotactic Calculator
   rather than our own model, which is circular.
3. False friends via CLICS colexification data. A purely phonological English-ish is readable with
   a sound-correspondence cheat sheet; drift is what makes related languages treacherous.
4. Audio. You can't un-know English, but you can hear a language with English's phonology and
   prosody and zero meaning.
5. The evolve path: sound changes over English, with a diachronic slider. Gets morphology,
   phonotactics, function words, exact frequency monotonicity and a language family for free.

## License

MIT. Note the data sources carry share-alike terms (wordfreq's data is CC BY-SA 4.0, UniMorph
CC BY-SA 3.0, LDNOOBW CC BY 4.0, SCOWL permissive, dsojevic MIT), and `public/lexicon.json` is
derived from them.
