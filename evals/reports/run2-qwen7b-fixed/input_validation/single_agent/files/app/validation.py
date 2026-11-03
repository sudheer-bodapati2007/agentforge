from typing import Dict

def validate_registration(data: Dict[str, str]) -> Dict[str, str]:
    if not isinstance(data, dict):
        raise TypeError('data must be a dictionary')

    username = data.get('username')
    email = data.get('email')
    age = data.get('age')

    if username is None:
        raise ValueError('username is missing')
    if not (3 <= len(username.strip()) <= 20) or not username.strip().isalnum() or '_' not in username.strip():
        raise ValueError('username is invalid')

    if email is None:
        raise ValueError('email is missing')
    if '@' not in email.strip() or email.strip().count('@') != 1 or email.strip().index('@') == 0 or email.strip().index('@') == len(email.strip()) - 1 or email.strip().index('.') == 0 or email.strip().index('.') == len(email.strip()) - 1:
        raise ValueError('email is invalid')

    if age is None:
        raise ValueError('age is missing')
    try:
        age = int(age)
    except ValueError:
        raise ValueError('age is invalid')
    if not (13 <= age <= 120):
        raise ValueError('age is invalid')

    return {
        'username': username.strip().lower(),
        'email': email.strip().lower(),
        'age': age
    }