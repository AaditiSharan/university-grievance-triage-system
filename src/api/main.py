"""FastAPI application for UniResolve AI."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.routers import admin, auth, rms, staff
from src.db.connection import create_tables
from src.rules.sensitivity_engine import load_config as load_sensitivity_config

app = FastAPI(
    title="UniResolve AI API",
    description="Explainable grievance triage with human-controlled final decisions.",
    version="1.0.0",
)

raw_origins = os.getenv("FRONTEND_ORIGINS", "").strip()
if raw_origins == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    frontend_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if not frontend_origins:
        frontend_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api")
app.include_router(rms.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(staff.router, prefix="/api")


@app.on_event("startup")
def initialize_database() -> None:
    create_tables()
    # Refuse to start with an invalid rules file instead of failing on a student's submission.
    load_sensitivity_config()


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve built frontend if available (for single-container/monolithic deployments)
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (frontend_dist / "index.html").exists():
    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
else:
    @app.get("/")
    def root():
        return {
            "message": "UniResolve AI API is running. Access /docs for API documentation or deploy the frontend."
        }
