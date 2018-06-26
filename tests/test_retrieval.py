from .context import englishish
corpus = englishish.download_corpus

import requests


def test_there_are_26_unique_ngram_urls():
    assert len(set(corpus.ngram_urls())) == 26


def test_ngram_urls_exist():
    for url in corpus.ngram_urls():
        r = requests.head(url)
        assert r.status_code == 200


def test_strip_tags_keeps_words():
    assert corpus.strip_tags("adonted") == "adonted"


def test_strip_tags_keeps_apostrophe():
    assert corpus.strip_tags("Agosi'n") == "Agosi'n"


def test_strip_tags_removes_pos_tag():
    assert corpus.strip_tags("Aised_VERB") == "Aised"
    assert corpus.strip_tags("carafa_DET") == "carafa"
    assert corpus.strip_tags("zaralea_NOUN") == "zaralea"
    assert corpus.strip_tags("liaceous_ADJ") == "liaceous"
    assert corpus.strip_tags("arbetslöshet_X") == "arbetslöshet"


def test_strip_tags_removes_numeric_tag():
    assert corpus.strip_tags("Alaska.42") == "Alaska"
    assert corpus.strip_tags("arises.3_NOUN") == "arises"
