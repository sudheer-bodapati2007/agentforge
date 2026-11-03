from app.validation import validate_registration

import pytest


def test_validate_registration_valid_data():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' example@example.com ',
        'age': 25
    }
    result = validate_registration(data)
    assert result == {
        'username': 'johndoe_123',
        'email': 'example@example.com',
        'age': 25
    }


def test_validate_registration_missing_username():
    data = {
        'email': ' example@example.com ',
        'age': 25
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'username is invalid'


def test_validate_registration_invalid_username():
    data = {
        'username': 'johndoe12345678901234567890',
        'email': ' example@example.com ',
        'age': 25
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'username is invalid'


def test_validate_registration_missing_email():
    data = {
        'username': ' JohnDoe_123 ',
        'age': 25
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'email is invalid'


def test_validate_registration_invalid_email():
    data = {
        'username': ' JohnDoe_123 ',
        'email': 'example@example',
        'age': 25
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'email is invalid'


def test_validate_registration_missing_age():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' example@example.com '
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'age is invalid'


def test_validate_registration_invalid_age_type():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' example@example.com ',
        'age': '25'
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'age is invalid'


def test_validate_registration_invalid_age_value():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' example@example.com ',
        'age': 12
    }
    with pytest.raises(ValueError) as exc_info:
        validate_registration(data)
    assert str(exc_info.value) == 'age is invalid'


def test_validate_registration_non_dict_input():
    with pytest.raises(TypeError) as exc_info:
        validate_registration('not a dict')
    assert str(exc_info.value) == 'data is not a dictionary'