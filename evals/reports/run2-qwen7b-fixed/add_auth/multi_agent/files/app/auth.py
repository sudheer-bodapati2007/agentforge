import os
import hmac
from fastapi import Depends, HTTPException

NOTES_API_KEY = os.getenv("NOTES_API_KEY")

if not NOTES_API_KEY:
    raise ValueError("NOTES_API_KEY environment variable is not set")

async def authenticate_api_key(api_key: str):
    if not api_key or not hmac.compare_digest(api_key, NOTES_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
