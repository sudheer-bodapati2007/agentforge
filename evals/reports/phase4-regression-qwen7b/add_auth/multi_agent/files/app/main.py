from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from app.auth import validate_api_key

app = FastAPI()
_notes: list[dict] = []

class NoteIn(BaseModel):
    text: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/notes")
def list_notes(api_key: str = Depends(validate_api_key)):
    return _notes

@app.post("/notes", status_code=201)
def add_note(note: NoteIn, api_key: str = Depends(validate_api_key)):
    item = {"id": len(_notes) + 1, "text": note.text}
    _notes.append(item)
    return item