import pytest
from app.slug import slugify


def test_slugify_with_string_input():
    assert slugify('Hello World') == 'hello-world'


def test_slugify_with_non_string_input():
    with pytest.raises(TypeError):
        slugify(123)


def test_slugify_with_lowercase_conversion():
    assert slugify('Hello World') == 'hello-world'


def test_slugify_with_non_alphanumeric_replacement():
    assert slugify('Hello, World!') == 'hello-world'


def test_slugify_with_leading_and_trailing_hyphens_removal():
    assert slugify('--Hello, World!--') == 'hello-world'