import pytest
from app.slug import slugify


def test_slugify_with_string():
    assert slugify('Hello World') == 'hello-world'


def test_slugify_with_non_string():
    with pytest.raises(TypeError):
        slugify(123)


def test_slugify_with_special_characters():
    assert slugify('Hello, World!') == 'hello-world'


def test_slugify_with_leading_and_trailing_hyphens():
    assert slugify('--Hello-World--') == 'hello-world'
