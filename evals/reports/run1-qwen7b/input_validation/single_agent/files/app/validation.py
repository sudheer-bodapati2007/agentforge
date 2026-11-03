from typing import Dict

def validate_registration(data: Dict) -> Dict:
    if not isinstance(data, dict):
        raise TypeError('data must be a dictionary')

    username = data.get('username')
    if username is None or not (3 <= len(username.strip()) <= 20) or not username.strip().isalnum() and not '_' in username.strip():
        raise ValueError('username is invalid')

    email = data.get('email')
    if email is None or '@' not in email.strip() or email.strip().count('@') != 1 or email.strip().index('@') == 0 or email.strip().index('@') == len(email.strip()) - 1 or '.' not in email.strip() or email.strip().index('.') == 0 or email.strip().index('.') == len(email.strip()) - 1:
        raise ValueError('email is invalid')

    age = data.get('age')
    if age is None or not isinstance(age, int) or not (13 <= age <= 120):
        raise ValueError('age is invalid')

    return {
        'username': username.strip().lower(),
        'email': email.strip().lower(),
        'age': age
    }