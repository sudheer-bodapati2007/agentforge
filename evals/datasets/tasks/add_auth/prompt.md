Here is a small FastAPI notes app in `app/main.py`. Add API-key authentication and return the complete updated `app/main.py`.

Requirements:
- Every `/notes` endpoint requires the request header `X-API-Key` to equal the value of the environment variable `NOTES_API_KEY`. Read the variable when each request is handled, not when the module is imported.
- A missing or wrong key gets status 401.
- If `NOTES_API_KEY` is unset or empty, every `/notes` request gets 401: access is never allowed without a configured key.
- `GET /health` stays public.
- Do not hardcode any key. Compare keys in constant time with `hmac.compare_digest`.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
_notes: list[dict] = []


class NoteIn(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/notes")
def list_notes():
    return _notes


@app.post("/notes", status_code=201)
def add_note(note: NoteIn):
    item = {"id": len(_notes) + 1, "text": note.text}
    _notes.append(item)
    return item
```
