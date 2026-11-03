import os
from fastapi import Depends, HTTPException
from hmac import compare_digest

NOTES_API_KEY = os.getenv('NOTES_API_KEY', '')

async def authenticate_api_key(api_key: str):
    if not compare_digest(api_key, NOTES_API_KEY):
        raise HTTPException(status_code=401, detail='Invalid API key')
    return api_key
