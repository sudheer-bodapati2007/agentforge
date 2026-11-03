import re

_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _email_ok(email: str) -> bool:
    if email.count("@") != 1:
        return False
    local, domain = email.split("@")
    dot = domain.find(".")
    return bool(local) and 0 < dot and not domain.endswith(".")


def validate_registration(data: dict) -> dict:
    if not isinstance(data, dict):
        raise TypeError("data must be a dict")
    for key in ("username", "email", "age"):
        if key not in data:
            raise ValueError(f"{key} is required")

    username = data["username"]
    if not isinstance(username, str) or not _USERNAME.match(username.strip()):
        raise ValueError("username is invalid")
    email = data["email"]
    if not isinstance(email, str) or not _email_ok(email.strip()):
        raise ValueError("email is invalid")
    age = data["age"]
    if type(age) is not int or not 13 <= age <= 120:
        raise ValueError("age is invalid")

    return {"username": username.strip().lower(), "email": email.strip().lower(), "age": age}
