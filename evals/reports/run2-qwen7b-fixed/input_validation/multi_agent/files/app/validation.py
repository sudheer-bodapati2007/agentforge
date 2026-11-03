from typing import Dict



def validate_registration(data: Dict) -> Dict:
    if not isinstance(data, dict):
        raise TypeError('data must be a dictionary')

    username = data.get('username')
    email = data.get('email')
    age = data.get('age')

    if username is None:
        raise ValueError('username is missing')
    if not (3 <= len(username) <= 20) or not username.isalnum() or '_' not in username:
        raise ValueError('username is invalid')

    if email is None:
        raise ValueError('email is missing')
    if email.count('@') != 1 or email.index('@') == 0 or email.index('@') == len(email) - 1 or email.index('.') == 0 or email.index('.') == len(email) - 1:
        raise ValueError('email is invalid')

    if age is None:
        raise ValueError('age is missing')
    if not isinstance(age, int) or age < 13 or age > 120:
        raise ValueError('age is invalid')

    return {
        'username': username.strip().lower(),
        'email': email.strip().lower(),
        'age': age
    }