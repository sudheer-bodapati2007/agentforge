In `app/validation.py`, write a function `validate_registration(data: dict) -> dict` that validates a user registration.

`data` has the keys `username`, `email` and `age`. Return a new dict with exactly these keys:
- `username`: stripped of surrounding whitespace and lowercased,
- `email`: stripped of surrounding whitespace and lowercased,
- `age`: the age as an `int`.

Rules (check the fields in the order username, email, age):
- `username`, after stripping, must be 3 to 20 characters long and contain only letters, digits and underscores.
- `email`, after stripping, must contain exactly one `@`, with at least one character before it, and the part after it must contain a dot that is neither its first nor its last character.
- `age` must be an `int` (a `bool` or a string is not accepted) between 13 and 120 inclusive.

When a key is missing or a rule is broken, raise `ValueError` with a message that contains the name of the first invalid field (for example "email is invalid"). If `data` is not a dict, raise `TypeError`.
