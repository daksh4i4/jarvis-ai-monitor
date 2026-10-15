import secrets
from fastapi import Header, HTTPException
from .config import API_TOKEN

async def require_token(authorization: str = Header(default="")):
    if not API_TOKEN:
        raise HTTPException(503, "Set JARVIS_API_TOKEN in environment.")
    if not secrets.compare_digest(authorization, f"Bearer {API_TOKEN}"):
        raise HTTPException(401, "Unauthorized")
