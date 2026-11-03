import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()
_notes: list[dict] = []


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("NOTES_API_KEY", "")
    if not expected or x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


class NoteIn(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/notes", dependencies=[Depends(require_api_key)])
def list_notes():
    return _notes


@app.post("/notes", status_code=201, dependencies=[Depends(require_api_key)])
def add_note(note: NoteIn):
    item = {"id": len(_notes) + 1, "text": note.text}
    _notes.append(item)
    return item
