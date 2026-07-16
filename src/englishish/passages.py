"""Build public/passages.json -- the corpus the site samples from on every load.

    uv run python -m englishish.passages

Three of these books (Alice, Moby-Dick, Pride and Prejudice) were committed to this repo in 2019
and sat unused. They're the original corpus, put to the job they were downloaded for.

REGISTER VARIETY IS THE POINT, not raw size. Nation (2006) measured the same vocabulary giving
very different coverage by genre -- 2,000 word families cover 87.83% of novels but only 83.07% of
newspapers. So a passage from Darwin and a passage from Alice at the same slider setting should
feel measurably different, and showing that variance is more interesting than showing one text.

Everything here is public domain. Project Gutenberg's position is explicit: strip their header and
trademark and the underlying text carries no restrictions.

Gutenberg is a volunteer-funded archive, so: one request per book, cached in data/ (gitignored) so
a rebuild never refetches, and a delay between fetches. Don't remove those.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "books"
OUT = Path(__file__).resolve().parents[2] / "public" / "passages"
SHARDS = 26              # the page shows ONE passage, so it should download ~one shard, not 2,600
SEED = 0xE4611
MAX_PASSAGES = 2600      # ~1MB raw, ~350KB gzipped. Effectively infinite for a toy.
PER_BOOK_CAP = 70        # keep any one book from dominating the sample
UA = "englishish/0.1 (+https://englishish.vercel.app) one-off corpus build"

# (gutenberg id, title, author, register). Chosen for spread, not popularity: the slider is far
# more interesting when Darwin and Alice disagree about what 2,000 words buys you.
BOOKS: list[tuple[int, str, str, str]] = [
    # 19th-century fiction
    (1342, "Pride and Prejudice", "Jane Austen", "fiction"),
    (2701, "Moby-Dick", "Herman Melville", "fiction"),
    (11, "Alice's Adventures in Wonderland", "Lewis Carroll", "children's"),
    (98, "A Tale of Two Cities", "Charles Dickens", "fiction"),
    (1400, "Great Expectations", "Charles Dickens", "fiction"),
    (84, "Frankenstein", "Mary Shelley", "fiction"),
    (345, "Dracula", "Bram Stoker", "fiction"),
    (174, "The Picture of Dorian Gray", "Oscar Wilde", "fiction"),
    (768, "Wuthering Heights", "Emily Brontë", "fiction"),
    (1260, "Jane Eyre", "Charlotte Brontë", "fiction"),
    (158, "Emma", "Jane Austen", "fiction"),
    (161, "Sense and Sensibility", "Jane Austen", "fiction"),
    (25344, "The Scarlet Letter", "Nathaniel Hawthorne", "fiction"),
    (219, "Heart of Darkness", "Joseph Conrad", "fiction"),
    (2814, "Dubliners", "James Joyce", "fiction"),
    (64317, "The Great Gatsby", "F. Scott Fitzgerald", "fiction"),
    (1184, "The Count of Monte Cristo", "Alexandre Dumas", "fiction"),
    (2600, "War and Peace", "Leo Tolstoy", "fiction"),
    (1399, "Anna Karenina", "Leo Tolstoy", "fiction"),
    (2554, "Crime and Punishment", "Fyodor Dostoyevsky", "fiction"),
    # adventure, mystery, early science fiction
    (120, "Treasure Island", "Robert Louis Stevenson", "adventure"),
    (1661, "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "mystery"),
    (164, "Twenty Thousand Leagues Under the Sea", "Jules Verne", "adventure"),
    (35, "The Time Machine", "H. G. Wells", "science fiction"),
    (36, "The War of the Worlds", "H. G. Wells", "science fiction"),
    (43, "The Strange Case of Dr Jekyll and Mr Hyde", "Robert Louis Stevenson", "fiction"),
    (74, "The Adventures of Tom Sawyer", "Mark Twain", "children's"),
    (76, "Adventures of Huckleberry Finn", "Mark Twain", "fiction"),
    (16, "Peter Pan", "J. M. Barrie", "children's"),
    (55, "The Wonderful Wizard of Oz", "L. Frank Baum", "children's"),
    (271, "Black Beauty", "Anna Sewell", "children's"),
    (113, "The Secret Garden", "Frances Hodgson Burnett", "children's"),
    # science, philosophy, economics, history -- the registers that break the slider
    (2009, "On the Origin of Species", "Charles Darwin", "science"),
    (1228, "On the Origin of Species (1st ed.)", "Charles Darwin", "science"),
    (3300, "The Wealth of Nations", "Adam Smith", "economics"),
    (1497, "The Republic", "Plato", "philosophy"),
    (1232, "The Prince", "Niccolò Machiavelli", "philosophy"),
    (3207, "Leviathan", "Thomas Hobbes", "philosophy"),
    (4363, "Beyond Good and Evil", "Friedrich Nietzsche", "philosophy"),
    (205, "Walden", "Henry David Thoreau", "essay"),
    (132, "The Art of War", "Sun Tzu", "philosophy"),
    (5827, "The Problems of Philosophy", "Bertrand Russell", "philosophy"),
    (14975, "The Voyage of the Beagle", "Charles Darwin", "science"),
    (1080, "A Modest Proposal", "Jonathan Swift", "essay"),
    (15491, "The Autobiography of Benjamin Franklin", "Benjamin Franklin", "memoir"),
    (2680, "Meditations", "Marcus Aurelius", "philosophy"),
]


def fetch(book_id: int) -> str | None:
    """Gutenberg plaintext, cached. One request per book, ever."""
    DATA.mkdir(parents=True, exist_ok=True)
    cached = DATA / f"{book_id}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace")
    url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"    !! {book_id}: {e}")
        return None
    # Gutenberg serves CRLF, and .decode() does NOT translate newlines the way read_text() does.
    # Without this the paragraph splitter sees one \r\n\r\n-separated blob and finds nothing, so
    # the build silently yields zero passages on a cache MISS and works fine on a cache HIT.
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    cached.write_text(body, encoding="utf-8")
    time.sleep(1.0)  # be a decent citizen; this only runs on a cache miss
    return body


START_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.S)
END_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK")


def strip_gutenberg(text: str) -> str:
    """Drop the header/footer. Gutenberg's terms: without their trademark, the text is just PD."""
    m = START_RE.search(text)
    if m:
        text = text[m.end() :]
    m = END_RE.search(text)
    if m:
        text = text[: m.start()]
    return text


HEADING_RE = re.compile(r"^(chapter|book|part|volume|act|scene|canto|letter|section)\b", re.I)
ROMAN_RE = re.compile(r"^[IVXLCDM]+\.?$")
BAD_RE = re.compile(r"(_|\[|\]|\{|\}|\||\*|>{2}|https?://|@|\d{4}\s*,\s*\d)")


def paragraphs(text: str) -> list[str]:
    """Blank-line-separated paragraphs, whitespace normalized."""
    out = []
    for chunk in re.split(r"\n[ \t]*\n", text):
        p = re.sub(r"\s+", " ", chunk).strip()
        if p:
            out.append(p)
    return out


def usable(p: str) -> bool:
    """Is this a self-contained paragraph of ordinary prose?

    The filters exist because Gutenberg plaintext is full of things that aren't prose: chapter
    headings, tables of contents, transcriber's notes, underscore-delimited italics, roman
    numerals, verse. Any of those in the sample makes the toy look broken rather than hard.
    """
    if not (220 <= len(p) <= 900):
        return False
    if p[-1] not in ".?!”\"'":
        return False
    if not (p[0].isupper() or p[0] in "“\"'"):
        return False
    if HEADING_RE.match(p) or ROMAN_RE.match(p.split()[0]):
        return False
    if BAD_RE.search(p):
        return False
    words = p.split()
    if len(words) < 35:
        return False
    # Runs of capitalised words are headings, not sentences.
    caps = sum(1 for w in words if len(w) > 2 and w.isupper())
    if caps > 1:
        return False
    # Mostly letters, spaces and ordinary punctuation.
    ok = sum(1 for c in p if c.isalpha() or c in " ,.;:'’‘“”?!-—–()&")
    return ok / len(p) > 0.98


def main() -> None:
    rng = random.Random(SEED)
    print(f"building corpus from {len(BOOKS)} books (cached in {DATA.relative_to(DATA.parents[2])})\n")

    pool: list[tuple[str, str, str, str]] = []  # (text, title, author, register)
    got = failed = 0
    for book_id, title, author, register in BOOKS:
        raw = fetch(book_id)
        if not raw:
            failed += 1
            continue
        paras = [p for p in paragraphs(strip_gutenberg(raw)) if usable(p)]
        rng.shuffle(paras)
        keep = paras[:PER_BOOK_CAP]
        pool.extend((p, title, author, register) for p in keep)
        got += 1
        print(f"  {title[:42]:44} {register:16} {len(paras):>5} usable -> kept {len(keep)}")

    rng.shuffle(pool)
    pool = pool[:MAX_PASSAGES]

    # SHARD IT. The page renders exactly one passage, so shipping all 2,600 costs ~500KB gzipped
    # to use ~0.2KB of it. One random shard is ~20KB and is indistinguishable from the real thing:
    # random shard + random passage inside it is still uniform over the corpus.
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    entries = [{"t": t, "b": b, "a": a, "r": r} for t, b, a, r in pool]
    shards = [entries[i::SHARDS] for i in range(SHARDS)]
    for i, shard in enumerate(shards):
        (OUT / f"{i:02d}.json").write_text(
            json.dumps(shard, separators=(",", ":"), ensure_ascii=False)
        )
    (OUT / "manifest.json").write_text(
        json.dumps({"shards": SHARDS, "passages": len(entries), "books": got,
                    "source": "Project Gutenberg, public domain"}, separators=(",", ":"))
    )
    total = sum(f.stat().st_size for f in OUT.glob("*.json")) / 1024
    biggest = max(f.stat().st_size for f in OUT.glob("[0-9]*.json")) / 1024
    by_reg: dict[str, int] = {}
    for _t, _b, _a, r in pool:
        by_reg[r] = by_reg.get(r, 0) + 1
    print(f"\n{got} books ok, {failed} failed")
    print(f"wrote {SHARDS} shards + manifest: {len(pool):,} passages, {total:,.0f} KB total, "
          f"{biggest:,.0f} KB largest shard (that's the actual page cost)")
    print("  by register: " + "  ".join(f"{k}={v}" for k, v in sorted(by_reg.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
