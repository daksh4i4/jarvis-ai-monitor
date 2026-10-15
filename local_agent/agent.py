import os, secrets, subprocess, webbrowser
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

TOKEN = os.environ.get("LOCAL_AGENT_TOKEN", "")
ALLOWED_URLS = {"https://www.delta.exchange/", "https://www.tradingview.com/", "https://www.google.com/"}
ALLOWED_APPS = {}  # Add explicit executable paths only after reviewing security.
app = FastAPI(title="JARVIS Local Agent")

class Command(BaseModel):
    action: str
    target: str

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/command")
def command(body: Command, authorization: str = Header(default="")):
    if not TOKEN or not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "Unauthorized")
    if body.action == "open_url":
        if body.target not in ALLOWED_URLS:
            raise HTTPException(400, "URL not allowlisted.")
        webbrowser.open(body.target)
        return {"ok": True, "message": "Opened " + body.target}
    if body.action == "open_app":
        path = ALLOWED_APPS.get(body.target.lower())
        if not path:
            raise HTTPException(400, "App not allowlisted.")
        subprocess.Popen([path], shell=False)
        return {"ok": True, "message": "Opened " + body.target}
    raise HTTPException(400, "Action not allowed.")
