"""Search primitives: tokenisation, BM25 (sparse retrieval), reciprocal rank fusion and
cosine similarity. Pure functions; small enough to keep dependency-free."""

import math
import re
from collections import Counter
from collections.abc import Hashable, Sequence

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in into is it its me my "
    "of on or our should so that the their them then there these this to use used uses using "
    "was we what when where which who why will with you your".split()
)


# (suffix, replacement), longest first. A suffix is removed only if at least 4 letters
# remain (3 for a plain plural 's'), so short words keep their meaning.
_SUFFIXES = (
    ("ations", ""), ("ation", ""), ("ating", ""), ("ated", ""), ("ates", ""), ("ate", ""),
    ("ments", ""), ("ment", ""), ("ings", ""), ("ing", ""), ("ies", "y"), ("ied", "y"),
    ("ers", ""), ("er", ""), ("ed", ""), ("es", ""), ("ly", ""),
)


def _stem(word: str) -> str:
    """Light suffix stripping so inflections meet: authenticate / authenticated /
    authentication -> authentic, retries -> retry, validation -> valid."""
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)] + replacement
    if word.endswith("s") and not word.endswith("ss") and len(word) >= 4:
        return word[:-1]
    return word


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    """Lowercase word tokens; camelCase and snake_case identifiers are split into words."""
    tokens = []
    for raw in _WORD.findall(_CAMEL.sub(" ", text)):
        word = raw.lower()
        if keep_stopwords or word not in STOPWORDS:
            tokens.append(_stem(word))
    return tokens


class BM25:
    """Okapi BM25 over a fixed list of documents."""

    def __init__(self, documents: Sequence[list[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._docs = [Counter(doc) for doc in documents]
        self._lengths = [len(doc) for doc in documents]
        self._avg = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        self._k1, self._b = k1, b
        df: Counter[str] = Counter()
        for doc in self._docs:
            df.update(doc.keys())
        n = len(self._docs)
        self.idf = {term: math.log(1 + (n - count + 0.5) / (count + 0.5)) for term, count in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        terms = [t for t in dict.fromkeys(query) if t in self.idf]
        out = []
        for doc, length in zip(self._docs, self._lengths, strict=True):
            score = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    norm = self._k1 * (1 - self._b + self._b * length / (self._avg or 1))
                    score += self.idf[term] * tf * (self._k1 + 1) / (tf + norm)
            out.append(score)
        return out


def reciprocal_rank_fusion(rankings: Sequence[Sequence[Hashable]], k: int = 60) -> dict[Hashable, float]:
    """Combine ranked lists without comparing their raw scores (Cormack et al., 2009)."""
    fused: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    return fused


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector sizes differ ({len(a)} vs {len(b)})")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
