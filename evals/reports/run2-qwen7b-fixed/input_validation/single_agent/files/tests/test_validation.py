from app.validation import validate_registration
import pytest

@pytest.mark.parametrize('data, expected', [
    ({'username': 'JohnDoe', 'email': 'john.doe@example.com', 'age': '15'}, {'username': 'johndoe', 'email': 'johndoe@example.com', 'age': 15}),
    ({'username': 'Jane_Doe', 'email': 'jane.doe@example.com', 'age': '20'}, {'username': 'janedoe', 'email': 'janedoe@example.com', 'age': 20}),
    ({'username': 'j', 'email': 'j@example.com', 'age': '15'}, ValueError),
    ({'username': 'JohnDoe', 'email': 'j@example.com', 'age': '121'}, ValueError),
    ({'username': 'JohnDoe', 'email': 'j@example.com', 'age': 'abc'}, ValueError),
    ({'username': 'JohnDoe', 'email': 'j@example.com'}, ValueError),
    ({'username': 'JohnDoe', 'age': '15'}, ValueError),
    ({'email': 'j@example.com', 'age': '15'}, ValueError),
    ({'username': 'JohnDoe', 'email': 'j@example.com', 'age': '15', 'extra': 'data'}, ValueError),
    (None, TypeError)
])
def test_validate_registration(data, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            validate_registration(data)
    else:
        assert validate_registration(data) == expected