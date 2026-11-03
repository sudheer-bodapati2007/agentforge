from app.validation import validate_registration

import pytest


@pytest.mark.parametrize('data, expected', [
    ({'username': 'john_doe', 'email': 'john@example.com', 'age': 25}, {'username': 'johndoe', 'email': 'john@example.com', 'age': 25}),
    ({'username': 'j', 'email': 'john@example.com', 'age': 25}, ValueError),
    ({'username': 'john_doe', 'email': 'john@example', 'age': 25}, ValueError),
    ({'username': 'john_doe', 'email': 'john@example.com', 'age': 'twenty-five'}, ValueError),
    ({'username': 'john_doe', 'email': 'john@example.com'}, ValueError),
    ({'username': 'john_doe', 'age': 25}, ValueError),
    ({'email': 'john@example.com', 'age': 25}, ValueError),
    ({'username': 'john_doe', 'email': 'john@example.com', 'age': 121}, ValueError),
    ({'username': 'john_doe', 'email': 'john@example.com', 'age': 12}, ValueError),
    (123, TypeError),
    ({}, TypeError),
    (None, TypeError),
    ('not a dict', TypeError),
    (['not', 'a', 'dict'], TypeError),
    ({'username': 'john_doe', 'email': 'john@example.com', 'age': 25, 'extra': 'field'}, {'username': 'johndoe', 'email': 'john@example.com', 'age': 25}),
])
def test_validate_registration(data, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            validate_registration(data)
    else:
        assert validate_registration(data) == expected
