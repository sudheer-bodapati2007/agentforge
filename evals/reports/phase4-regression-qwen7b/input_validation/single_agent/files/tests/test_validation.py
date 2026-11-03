import pytest
from app.validation import validate_registration



def test_valid_registration():
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



def test_missing_username():
    data = {
        'email': ' john.doe@example.com ',
        'age': 25
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'username is missing'



def test_invalid_username():
    data = {
        'username': 'johndoe12345678901234567890',
        'email': ' john.doe@example.com ',
        'age': 25
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'username is invalid'



def test_missing_email():
    data = {
        'username': ' JohnDoe_123 ',
        'age': 25
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'email is missing'



def test_invalid_email():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' john.doe@example',
        'age': 25
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'email is invalid'



def test_missing_age():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' john.doe@example.com '
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'age is missing'



def test_invalid_age_type():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' john.doe@example.com ',
        'age': '25'
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'age is invalid'



def test_invalid_age_value():
    data = {
        'username': ' JohnDoe_123 ',
        'email': ' john.doe@example.com ',
        'age': 12
    }
    with pytest.raises(ValueError) as excinfo:
        validate_registration(data)
    assert str(excinfo.value) == 'age is invalid'
