"""
Seed Sprint 03 — Cria produto de teste e faz upload das 4 views.
Executar: docker compose exec api python backend/scripts/seed_sprint03.py
"""
import os
import sys
import requests
from pathlib import Path

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/api/v1")
EXAMPLES_DIR = Path("/app/examples/roupa")

VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"]
VIEW_FILES = {
    "frente": "frente.png",
    "costas": "costas.png",
    "lat_direita": "lat_direita.png",
    "lat_esquerda": "lat_esquerda.png",
}


def get_token() -> str:
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": os.getenv("ADMIN_EMAIL", "admin@confexai.local"),
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
    })
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def create_product(token: str) -> str:
    r = requests.post(
        f"{BASE_URL}/products",
        json={
            "name": "Peca Teste Sprint 03 — Lisa",
            "category": "blusa",
            "fabric": "viscose",
            "notes": "Peca de teste para validacao do pipeline de variacao de cor",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    product_id = r.json()["data"]["id"]
    print(f"✅ Produto criado: {product_id}")
    return product_id


def upload_images(token: str, product_id: str) -> dict[str, str]:
    image_ids = {}
    for view, filename in VIEW_FILES.items():
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            print(f"⚠️  Arquivo nao encontrado: {filepath}")
            continue

        with open(filepath, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/products/{product_id}/images/upload",
                files={"file": (filename, f, "image/png")},
                params={"view": view},
                headers={"Authorization": f"Bearer {token}"},
            )
        r.raise_for_status()
        image_id = r.json()["data"]["id"]
        image_ids[view] = image_id
        print(f"✅ Upload {view}: {image_id}")

    return image_ids


def main():
    print("=== Seed Sprint 03 ===")
    token = get_token()
    print(f"✅ Token obtido")

    product_id = create_product(token)
    image_ids = upload_images(token, product_id)

    print("\n=== IDs para usar nos proximos passos ===")
    print(f"PRODUCT_ID={product_id}")
    for view, img_id in image_ids.items():
        print(f"IMAGE_ID_{view.upper()}={img_id}")

    # Salvar IDs em arquivo para referencia
    with open("/app/scripts/sprint03_ids.txt", "w") as f:
        f.write(f"PRODUCT_ID={product_id}\n")
        for view, img_id in image_ids.items():
            f.write(f"IMAGE_ID_{view.upper()}={img_id}\n")
    print("\n✅ IDs salvos em backend/scripts/sprint03_ids.txt")


if __name__ == "__main__":
    main()
