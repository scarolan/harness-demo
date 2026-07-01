import platform
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs",
)

templates = Jinja2Templates(directory="app/templates")

start_time = datetime.now(timezone.utc)


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
            "hostname": platform.node(),
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
        "hostname": platform.node(),
        "python_version": platform.python_version(),
    }


@app.get("/api/user")
def get_user(user_id: str):
    import sqlite3
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
    except sqlite3.Error:
        return {"error": "database unavailable"}
    if result is None:
        return {"error": "user not found"}
    return {"user": result}
