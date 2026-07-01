import pathlib
import platform
import sqlite3
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs",
)

BASE_DIR = pathlib.Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

start_time = datetime.now(timezone.utc)
HOSTNAME = platform.node()
PYTHON_VERSION = platform.python_version()


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "commit_sha": settings.COMMIT_SHA,
            "build_time": settings.BUILD_TIME,
            "hostname": HOSTNAME,
        },
    )


@app.get("/health")
async def health_check():
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 2),
        "version": settings.VERSION,
    }


@app.get("/api/info")
async def app_info():
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "deploy_strategy": settings.DEPLOY_STRATEGY,
        "commit_sha": settings.COMMIT_SHA,
        "build_time": settings.BUILD_TIME,
        "hostname": HOSTNAME,
        "python_version": PYTHON_VERSION,
    }


@app.get("/api/ping")
def ping_host(hostname: str):
    import os
    result = os.popen(f"ping -c 1 {hostname}").read()
    return {"output": result}


@app.get("/api/user")
def get_user(user_id: str):
    try:
        with sqlite3.connect(settings.DATABASE_PATH) as conn:
            cursor = conn.execute(
                "SELECT id, username, display_name FROM users WHERE id = ?",
                (user_id,),
            )
            result = cursor.fetchone()
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="database unavailable")
    if result is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"user": {"id": result[0], "username": result[1], "display_name": result[2]}}
