"""Hidden reference tests for the write_tests task: the given behaviour must be unchanged,
including the parts a model might be tempted to "improve" (non-ASCII letters are dropped)."""

import pytest

from app.slug import slugify


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello, World!", "hello-world"),
        ("  Many   spaces  ", "many-spaces"),
        ("Already-slugged", "already-slugged"),
        ("A1 b2", "a1-b2"),
        ("Ünïcode", "n-code"),
        ("under_score", "under-score"),
        ("", ""),
        ("---", ""),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


@pytest.mark.parametrize("value", [None, 123, b"bytes"])
def test_non_string_is_type_error(value):
    with pytest.raises(TypeError):
        slugify(value)
