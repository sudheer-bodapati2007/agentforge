Here is `app/slug.py`. Keep its behaviour exactly as it is (you may only reformat it), include it in your answer, and write thorough pytest tests for it in `tests/test_slug.py`.

```python
import re


def slugify(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return slug.strip("-")
```
