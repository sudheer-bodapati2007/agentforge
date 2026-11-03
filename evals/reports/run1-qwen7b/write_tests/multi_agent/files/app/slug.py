def slugify(text):
    if not isinstance(text, str):
        raise TypeError('Input must be a string')
    return '-'.join(text.lower().split())