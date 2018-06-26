"""
Retrieve the Ngram files produced by the Google Books project and use them
to produce a large corpus of words with their relative frequencies.
"""

from collections import Counter
import gzip
import io
import logging
import re
import requests
import string


DEST_FILE = "../data/word_counts.csv"


def main():
    with open(DEST_FILE, 'w') as csv:
        for url in ngram_urls():
            data = retrieve(url)
            logging.info(f"retrieved {url}")
            lines = lines_from_zipped(data)
            cleaned = rewrite_without_year_or_tag(lines)
            for word, count in filter_on_frequency(cleaned):
                csv.write(f"{word}\t{count}\n")
            print(f"Finished up to {word}")


def filter_on_frequency(word_occurences):
    for word, appearance_count, corpus_count in word_occurences:
        if corpus_count > 100:
            yield word, appearance_count


def rewrite_without_year_or_tag(ngram_file):
    word, appearances, corpora = None, 0, 0

    for line in ngram_file:
        w, _, a, c = line.split()
        w, a, c = strip_tags(w), int(a), int(c)
        if w != word:
            if word is not None:
                yield word, appearances, corpora
            word, appearances, corpora = w, a, c
        else:
            appearances += a
            corpora += c

    if word is not None:
        yield word, appearances, corpora


def build_frequency_table(ngram_counts):
    corpora_count = Counter()
    appearance_count = Counter()

    for line in ngram_counts:
        word, _, appearances, corpora = line.split()  # skip year field
        word = strip_tags(word)
        corpora_count[word] += corpora
        appearance_count[word] += appearances

    # filter for words that appear in a minimum number of corpora
    return {word: appearance_count[word] for word, corpora in corpora_count.items() if corpora >= 10}


def strip_tags(word):
    if "_" in word:
        word = word[:word.find("_")]
    match = re.match(r"(.+)\.\d", word)
    if match:
        word = match.group(1)
    return word


def write_table(table, filename):
    with open(filename, 'w') as outfile:
        for key, value in table.items():
            outfile.write(f"{key}\t{value}\n")


def ngram_urls():
    """Generator for the URLs for the Google 1-grams that start with a letter."""
    base_url = "http://storage.googleapis.com/books/ngrams/books/googlebooks-eng-all-1gram-20120701-{}.gz"
    for letter in string.ascii_lowercase:
        yield base_url.format(letter)


def retrieve(url):
    """Get binary data from a specified URL."""
    r = requests.get(url)
    if r.status_code != 200:
        logging.error(
            f"HTTP response code {r.status_code}. Unable to download {url}")
        raise FileNotFoundError
    else:
        logging.info(f"Finished downloading {len(r.content)} bytes from {url}")
        return r.content


def lines_from_zipped(data):
    for line in io.BytesIO(gzip.decompress(data)):
        yield line.decode("utf-8")


if __name__ == "__main__":
    main()
