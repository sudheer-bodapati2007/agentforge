from app.validation import validate_registration

import pytest



def test_validate_registration_with_valid_data():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' john.doe@example.com ',
        'age': 25
    }
    result = validate_registration(data)
    assert result == {
        'username': 'johndoe_123',
        'email': 'john.doe@example.com',
        'age': 25
    }


def test_validate_registration_with_invalid_username():
    data = {
        'username': 'j',
        'email': 'john.doe@example.com',
        'age': 25
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'username is invalid'


def test_validate_registration_with_invalid_email():
    data = {
        'username': 'johndoe_123',
        'email': 'john.doe@example',
        'age': 25
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'email is invalid'


def test_validate_registration_with_invalid_age():
    data = {
        'username': 'johndoe_123',
        'email': 'john.doe@example.com',
        'age': 12
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'age is invalid'


def test_validate_registration_with_non_dict_data():
    data = 'not a dict'
    with pytest.raises(TypeError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'data is not a dictionary'
