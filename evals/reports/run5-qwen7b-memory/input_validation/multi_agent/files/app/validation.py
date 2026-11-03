from typing import Dict


def validate_registration(data: Dict) -> Dict:
    if not isinstance(data, dict):
        raise TypeError('data is not a dictionary')

    username = data.get('username')
    if username is None or not (3 <= len(username) <= 20) or not username.isalnum() and not '_' in username:
        raise ValueError('username is invalid')

    email = data.get('email')
    if email is None or email.count('@') != 1 or email.index('@') == 0 or email.index('@') == len(email) - 1 or email.index('.') == 0 or email.index('.') == len(email) - 1:
        raise ValueError('email is invalid')

    age = data.get('age')
    if age is None or not isinstance(age, int) or not (13 <= age <= 120):
        raise ValueError('age is invalid')

    return {
        'username': username.strip().lower(),
        'email': email.strip().lower(),
        'age': age
    }