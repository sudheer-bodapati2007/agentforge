from app.slug import slugify
import pytest


def test_slugify_with_string():
    assert slugify('Hello World') == 'hello-world'


def test_slugify_with_empty_string():
    assert slugify('') == ''


def test_slugify_with_non_string_input():
    with pytest.raises(TypeError):
        slugify(123)