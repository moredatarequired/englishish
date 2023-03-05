# first we need a file that has a bunch of words
TEXT_SAMPLE = "books/moby.txt"

import string
# functions to simplify the text


def corral(line):
    for word in line.split():
        word = word.strip().lower()
        while word and word[-1] in string.punctuation:
            word = word[:-1]
        if word and all(c in string.ascii_lowercase or c == "'" for c in word):
            yield word


# simple word count:
from collections import defaultdict, Counter

word_count = Counter()
with open(TEXT_SAMPLE) as infile:
    for line in infile:
        word_count.update(corral(line))

real_words = set(word_count.keys())

# cool, now just build a character-level model
transition = defaultdict(Counter)
for word, count in word_count.items():
    transition[""][word[0]] += count  # 0 characters
    if len(word) > 1:
        transition[word[0]][word[1]] += count  # 1 character
    if len(word) > 2:
        transition[word[0:2]][word[2]] += count  # 2 characters
    for i in range(len(word) - 3):
        transition[word[i:i+3]][word[i+3]] += count  # 3 characters
    transition[word[-3:]][None] += count


from numpy import random


def get_next(current_string):
    table = transition[current_string]
    total = sum(table.values())
    return random.choice(list(table.keys()), p=[v / total for v in table.values()])


def produce_word():
    word = get_next("")
    while True:
        c = get_next(word[-3:])
        if c is None:
            return word
        word += c


def produce_nonsense_word():
    while True:
        w = produce_word()
        if w not in real_words:
            return w


print(" ".join(produce_nonsense_word() for _ in range(10)))


# producing this demo took almost exactly 40 minutes of programming.
# therefore: I should stop dragging my feet, this project isn't that hard
