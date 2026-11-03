def validate_registration(data):
    if not isinstance(data, dict):
        raise TypeError('Input must be a dictionary')

    username = data.get('username', '').strip().lower()
    email = data.get('email', '').strip().lower()
    age = data.get('age', None)

    if not username:
        raise ValueError('Username is required')
    if len(username) < 3 or len(username) > 20:
        raise ValueError('Username must be between 3 and 20 characters long')
    if not username.isalnum():
        raise TypeError('Username must contain only alphanumeric characters')

    if not email:
        raise ValueError('Email is required')
    if email.count('@') != 1:
        raise ValueError('Email must contain exactly one @')
    local_part, domain_part = email.split('@')
    if not local_part or not domain_part:
        raise ValueError('Email must have a non-empty local part and a valid domain part')

    if not age:
        raise ValueError('Age is required')
    try:
        age = int(age)
    except ValueError:
        raise ValueError('Age must be an integer')
    if age < 13 or age > 120:
        raise ValueError('Age must be between 13 and 120 inclusive')

    return {
        'username': username,
        'email': email,
        'age': age
    }