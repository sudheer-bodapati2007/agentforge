from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from hmac import compare_digest
import os

app = FastAPI()
_notes: list[dict] = []

class NoteIn(BaseModel):
    text: str

async def verify_api_key(api_key: str):
    notes_api_key = os.getenv('NOTES_API_KEY')
    if not notes_api_key or not compare_digest(notes_api_key, api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/notes")
def list_notes(api_key: str = Depends(verify_api_key)):
    return _notes

@app.post("/notes", status_code=201)
def add_note(note: NoteIn, api_key: str = Depends(verify_api_key)):
    item = {"id": len(_notes) + 1, "text": note.text}
    _notes.append(item)
    return item