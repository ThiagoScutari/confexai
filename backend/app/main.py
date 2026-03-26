from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, auth, products, images, jobs

app = FastAPI(title="ConfexAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(images.router)
app.include_router(jobs.router)
