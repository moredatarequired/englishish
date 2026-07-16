"""English-ish: an alternate vocabulary as close to English as possible without being English.

    uv run python -m englishish.build     # rebuild lexicon.json
    uv run python -m englishish.render    # inspect the map, render at several vocab sizes

`lexicon.json` is the artifact boundary: everything upstream of build.py can be swapped out
without the frontend in web/ knowing. See README.md and FINDINGS.md.
"""

__all__ = ["build", "data", "filters", "morphology", "ngram", "render"]
