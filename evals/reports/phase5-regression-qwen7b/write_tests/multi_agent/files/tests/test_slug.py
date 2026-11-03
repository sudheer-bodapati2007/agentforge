import pytest
from app.slug import slugify


def test_slugify_raises_type_error_for_non_string_input():
    with pytest.raises(TypeError) as excinfo:
        slugify(123)
    assert str(excinfo.value) == 'text must be a string'


def test_slugify_converts_to_lowercase():
    assert slugify('Hello World') == 'hello-world'


def test_slugify_replaces_non_alphanumeric_characters_with_hyphens():
    assert slugify('Hello, World!') == 'hello-world'


def test_slugify_strips_leading_and_trailing_hyphens():
    assert slugify('--Hello-World--') == 'hello-world'


def test_slugify_handles_empty_string():
    assert slugify('') == ''


def test_slugify_handles_strings_with_only_non_alphanumeric_characters():
    assert slugify('!!!') == '-'


def test_slugify_handles_strings_with_multiple_consecutive_non_alphanumeric_characters():
    assert slugify('Hello,  World!') == 'hello--world'


def test_slugify_handles_strings_with_leading_and_trailing_non_alphanumeric_characters():
    assert slugify('--Hello,  World!--') == 'hello--world'