import re


def slugify(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return slug.strip("-")
