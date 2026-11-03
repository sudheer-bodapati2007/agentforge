from fastapi import Depends, HTTPException
from app.config import get_api_key
from hmac import compare_digest

async def validate_api_key(api_key: str = Depends(get_api_key)):
    notes_api_key = get_api_key()
    if not notes_api_key or not compare_digest(notes_api_key, api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
