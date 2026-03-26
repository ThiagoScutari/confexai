from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

from app.api import health, auth, products, images, jobs

app = FastAPI(title="ConfexAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# Servir uploads como assets estaticos
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(images.router)
app.include_router(jobs.router)
