"""Hidden reference tests for the input_validation task."""

import pytest

from app.validation import validate_registration


def valid(**changes):
    return {"username": "alice_1", "email": "alice@example.com", "age": 30, **changes}


def test_normalises_valid_input():
    result = validate_registration(valid(username="  Alice_1 ", email=" Alice@Example.COM "))
    assert result == {"username": "alice_1", "email": "alice@example.com", "age": 30}


def test_does_not_modify_the_input():
    data = valid(username=" Bob_2 ")
    validate_registration(data)
    assert data["username"] == " Bob_2 "


@pytest.mark.parametrize("username", ["abc", "a" * 20])
def test_username_length_boundaries_are_accepted(username):
    assert validate_registration(valid(username=username))["username"] == username


@pytest.mark.parametrize("username", ["ab", "a" * 21, "bad name", "bad-name", "", "   "])
def test_invalid_username(username):
    with pytest.raises(ValueError, match="(?i)username"):
        validate_registration(valid(username=username))


@pytest.mark.parametrize("email", ["no-at-sign", "a@@b.com", "@b.com", "a@.com", "a@com.", "a@com", "a@b@c.com"])
def test_invalid_email(email):
    with pytest.raises(ValueError, match="(?i)email"):
        validate_registration(valid(email=email))


def test_short_valid_email():
    assert validate_registration(valid(email="a@b.c"))["email"] == "a@b.c"


@pytest.mark.parametrize("age", [13, 120])
def test_age_boundaries_are_accepted(age):
    assert validate_registration(valid(age=age))["age"] == age


@pytest.mark.parametrize("age", [12, 121, -1, "30", 30.5, True, None])
def test_invalid_age(age):
    with pytest.raises(ValueError, match="(?i)age"):
        validate_registration(valid(age=age))


@pytest.mark.parametrize("missing", ["username", "email", "age"])
def test_missing_key(missing):
    data = valid()
    del data[missing]
    with pytest.raises(ValueError, match=f"(?i){missing}"):
        validate_registration(data)


def test_first_invalid_field_is_reported():
    with pytest.raises(ValueError, match="(?i)username"):
        validate_registration({"username": "x", "email": "bad", "age": 5})


@pytest.mark.parametrize("data", [None, "alice", ["alice"], 42])
def test_non_dict_is_type_error(data):
    with pytest.raises(TypeError):
        validate_registration(data)
