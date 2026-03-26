import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.auth import verify_password, create_access_token, hash_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@confexai.local")
ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    hash_password("admin123")  # trocar em producao via variavel de ambiente
)


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    if payload.email != ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")
    if not verify_password(payload.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")
    token = create_access_token({"sub": "admin", "email": payload.email})
    return {"data": {"access_token": token, "token_type": "bearer"}}
