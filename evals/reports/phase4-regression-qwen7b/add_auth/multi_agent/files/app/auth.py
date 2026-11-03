import os
from fastapi import Depends, HTTPException, status
from hmac import compare_digest

NOTES_API_KEY = os.getenv("NOTES_API_KEY")

if not NOTES_API_KEY:
    raise ValueError("NOTES_API_KEY environment variable is not set")

async def validate_api_key(api_key: str = Depends(lambda: api_key)):
    if not compare_digest(api_key, NOTES_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return api_key