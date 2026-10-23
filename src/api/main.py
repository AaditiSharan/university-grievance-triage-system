
"""FastAPI application for UniResolve AI."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import admin, auth, rms
from src.db.connection import create_tables

app = FastAPI(
    title="UniResolve AI API",
    description="Explainable grievance triage with human-controlled final decisions.",
    version="1.0.0",
)
frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
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


@app.on_event("startup")
def initialize_database() -> None:
    create_tables()


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
