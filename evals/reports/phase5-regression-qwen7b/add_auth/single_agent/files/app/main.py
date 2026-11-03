from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from hmac import compare_digest
import os

app = FastAPI()
_notes: list[dict] = []

class NoteIn(BaseModel):
    text: str

async def api_key_auth(api_key: str = Depends(lambda: request.headers.get('X-API-Key'))):
    notes_api_key = os.getenv('NOTES_API_KEY')
    if not notes_api_key or not compare_digest(notes_api_key, api_key):
        raise HTTPException(status_code=401, detail='Invalid or missing API key')

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/notes", dependencies=[Depends(api_key_auth)])
def list_notes():
    return _notes

@app.post("/notes", status_code=201, dependencies=[Depends(api_key_auth)])
def add_note(note: NoteIn):
    item = {"id": len(_notes) + 1, "text": note.text}
    _notes.append(item)
    return item