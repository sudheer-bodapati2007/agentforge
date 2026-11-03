import pytest
from app.slug import slugify


def test_slugify_with_string():
    assert slugify('Hello World') == 'hello-world'


def test_slugify_with_non_string():
    with pytest.raises(TypeError) as excinfo:
        slugify(123)
    assert str(excinfo.value) == 'text must be a string'


def test_slugify_with_special_characters():
    assert slugify('Hello, World!') == 'hello-world'


def test_slugify_with_leading_and_trailing_hyphens():
    assert slugify('--Hello-World--') == 'hello-world'
