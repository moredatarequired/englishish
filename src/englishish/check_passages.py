"""Verify no Gutenberg boilerplate or non-prose reaches the site.

    uv run python -m englishish.check_passages

Checks three things, in the order they can fail:

  1. Every book's LABEL matches what the file says it is. Non-negotiable: the IDs in passages.py
     were typed from memory, and two of the original 46 were wrong -- 14975 was labelled "The
     Voyage of the Beagle" but is Ida B. Wells's "Southern Horrors: Lynch Law in All Its Phases",
     and 15491 was labelled Franklin's Autobiography but is Hooke's "Micrographia". A toy that
     misattributes a landmark anti-lynching pamphlet to Charles Darwin is worse than a broken toy.

  2. The FULL usable pool per book is boilerplate-free -- not just the shipped sample. PER_BOOK_CAP
     takes a random 70, so checking only what shipped means random sampling is what's protecting
     you, which is not a property you can rely on across rebuilds.

  3. The shipped shards agree.

INDEPENDENCE MATTERS. This deliberately uses a BROADER signature set than passages.BOILERPLATE_RE
rather than importing it. A check that re-asks the filter's own question can only ever agree with
it -- exactly how `pissoids` shipped past a profanity scan that reported zero leaks, because `piss`
wasn't in the list the scan was reading from.

But broader is not the same as vaguer. An earlier version of this check matched generic English --
"scanned", "license", "prepared by", "donation" -- and produced 74 hits, every one a false positive
("a donation of one hundred piastres" in Dumas, "Charters are Donations of the Soveraign" in
Hobbes). Worse, `IRS\\b` with no LEADING word boundary matched the end of "chairs", "affairs" and
"theirs" 62 times. Noise hides signal; every pattern below is Gutenberg-specific or structural.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

from .passages import BOOKS, SKIP_LEADING, fetch, paragraphs, strip_gutenberg, usable

SHARDS = Path(__file__).resolve().parents[2] / "public" / "passages"

# Broader than the build filter, and Gutenberg-specific throughout.
SIGNS: dict[str, str] = {
    "gutenberg": r"(?i)gutenberg|pglaf|gutenberg-tm",
    "etext": r"(?i)\be-?texts?\b",
    "foundation": r"(?i)literary archive foundation|michael s\.? hart|501\(c\)\(3\)|\bIRS\b",
    "markers": r"\*\*\*\s*(START|END) OF",
    "meta headers": r"(?im)^(title|author|release date|posting date|language|character set|"
                    r"translator|illustrator|produced by|credits):",
    "transcriber": r"(?i)transcriber'?s?\s+note|distributed proofread|proofreading team|"
                   r"scanned images|online distributed",
    "editions blurb": r"(?i)several editions of this|various characteristics|preferred file|"
                      r"filenumber|click on any",
    "redistribution": r"(?i)no restrictions whatsoever|copy it, give it away|re-?use it under",
    "urls/email": r"(?i)https?://|www\.\S|\S+@\S+\.\S",
    "illustration": r"(?i)\[illustration|\{illustration|\[frontispiece",
}


def real_title(raw: str) -> str | None:
    m = re.search(r"The Project Gutenberg eBook of ([^\n]+?)(?:, by |\n|$)", raw)
    if m:
        return m.group(1).strip()
    m = re.search(r"^Title:\s*(.+)$", raw, re.M)
    return m.group(1).strip() if m else None


def titles_match(label: str, actual: str) -> bool:
    a = re.sub(r"[^a-z]", "", label.lower())
    b = re.sub(r"[^a-z]", "", actual.lower())
    return a[:14] in b or b[:14] in a or difflib.SequenceMatcher(None, a, b).ratio() > 0.6


def main() -> int:
    fails = 0

    print(f"1. LABELS — do {len(BOOKS)} books say what we claim they are?")
    unverifiable = []
    for book_id, title, author, _reg in BOOKS:
        raw = fetch(book_id)
        if not raw:
            print(f"   !! id {book_id} ({title}): could not fetch")
            fails += 1
            continue
        actual = real_title(raw)
        if actual is None:
            unverifiable.append((book_id, title))
        elif not titles_match(title, actual):
            print(f"   !! id {book_id}: labelled {title!r} but is {actual!r}")
            fails += 1
    print(f"   {len(BOOKS) - len(unverifiable) - fails}/{len(BOOKS)} verified against the file's own"
          f" title line")
    if unverifiable:
        # Alice and Moby-Dick were committed here in 2019 with the header hand-removed, so there's
        # no title line left to check against. Their content is verified by (2) instead.
        print(f"   {len(unverifiable)} have no title line (header pre-stripped): "
              + ", ".join(t for _i, t in unverifiable))

    print("\n2. FULL USABLE POOL — boilerplate reachable in any book?")
    pool_hits: dict[str, list[tuple[str, str, str]]] = {}
    total_usable = 0
    for book_id, title, _author, _reg in BOOKS:
        raw = fetch(book_id)
        if not raw:
            continue
        good = [p for p in paragraphs(strip_gutenberg(raw)) if usable(p)][SKIP_LEADING:]
        total_usable += len(good)
        for p in good:
            for name, pat in SIGNS.items():
                m = re.search(pat, p)
                if m:
                    pool_hits.setdefault(name, []).append((title, m.group(0), p))
    if pool_hits:
        n = sum(len(v) for v in pool_hits.values())
        print(f"   !! {n} hit(s) across {len(pool_hits)} signature(s) in {total_usable:,} usable")
        for name, v in pool_hits.items():
            print(f"      [{name}] {len(v)}")
            for t, m, p in v[:3]:
                print(f"        {t}: {m!r} — {p[:110]}")
        fails += n
    else:
        print(f"   clean across {total_usable:,} usable paragraphs from {len(BOOKS)} books")

    print("\n3. SHIPPED SHARDS — boilerplate in what's actually deployed?")
    files = sorted(SHARDS.glob("[0-9]*.json"))
    if not files:
        print("   !! no shards found — run englishish.passages first")
        return 1
    shipped = [p for f in files for p in json.loads(f.read_text())]
    ship_hits = [
        (name, p, re.search(pat, p["t"]).group(0))
        for p in shipped
        for name, pat in SIGNS.items()
        if re.search(pat, p["t"])
    ]
    if ship_hits:
        print(f"   !! {len(ship_hits)} hit(s) in {len(shipped):,} shipped passages")
        for name, p, m in ship_hits[:5]:
            print(f"      [{name}] {m!r} in {p['b']} — {p['t'][:90]}")
        fails += len(ship_hits)
    else:
        print(f"   clean across {len(shipped):,} shipped passages in {len(files)} shards")

    print()
    if fails:
        print(f"FAIL — {fails} problem(s)")
        return 1
    print("PASS — labels correct, no boilerplate in the pool or the shards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
