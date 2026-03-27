"""
Executa pipeline completo para as 4 views com 3 cores.
Ler IDs de backend/scripts/sprint03_ids.txt antes de rodar.
Executar: docker compose exec api python backend/scripts/run_pipeline_sprint03.py
"""
import os
import requests
import json
from pathlib import Path

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/api/v1")
COLORS = ["#696980", "#978b7b", "#9e987d"]
VIEWS = ["frente", "costas", "lat_direita", "lat_esquerda"]

# Ler IDs do arquivo de seed
ids_file = Path("/app/scripts/sprint03_ids.txt")
ids = dict(line.strip().split("=") for line in ids_file.read_text().splitlines())

PRODUCT_ID = ids["PRODUCT_ID"]
IMAGE_IDS = {
    "frente": ids["IMAGE_ID_FRENTE"],
    "costas": ids["IMAGE_ID_COSTAS"],
    "lat_direita": ids["IMAGE_ID_LAT_DIREITA"],
    "lat_esquerda": ids["IMAGE_ID_LAT_ESQUERDA"],
}


def get_token() -> str:
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": os.getenv("ADMIN_EMAIL", "admin@confexai.local"),
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
    })
    return r.json()["data"]["access_token"]


def run_pipeline(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    total_cost = 0
    results = []

    for view, image_id in IMAGE_IDS.items():
        print(f"\n=== Processando: {view} ===")

        # Passo 1: Remocao de fundo
        r = requests.post(
            f"{BASE_URL}/products/{PRODUCT_ID}/images/{image_id}/remove-background",
            headers=headers,
        )
        bg_data = r.json()["data"]
        print(f"  Fundo: {'skipped (ja transparente)' if bg_data.get('skipped') else 'removido'}")

        # Passo 2: Deteccao de regioes protegidas
        r = requests.post(
            f"{BASE_URL}/jobs/detect-protected-regions",
            json={"product_image_id": image_id},
            headers=headers,
        )
        detect_data = r.json()["data"]
        cost = detect_data.get("cost_cents", 0)
        total_cost += cost
        protected = detect_data.get("protected_regions", [])
        print(f"  Deteccao: has_protected={detect_data['has_protected_regions']} | custo: {cost}¢")

        # Passo 3: Variacao de cor (3 cores)
        r = requests.post(
            f"{BASE_URL}/jobs/color-variation",
            json={
                "product_image_id": image_id,
                "target_colors": COLORS,
                "protected_regions": protected,
            },
            headers=headers,
        )
        color_data = r.json()["data"]
        for res in color_data["results"]:
            cost = res.get("cost_cents", 0)
            total_cost += cost
            method = res.get("method", "?")
            print(f"  Cor {res['color_hex']}: {res['status']} | metodo: {method} | custo: {cost}¢")
            results.append(res)

    print(f"\n=== Resumo ===")
    print(f"Total de imagens geradas: {len([r for r in results if r['status'] == 'pending_review'])}/12")
    print(f"Custo total: {total_cost}¢ (~R$ {total_cost * 0.006:.2f})")

    # Salvar resultado
    with open("/app/scripts/sprint03_results.json", "w") as f:
        json.dump({"total_cost_cents": total_cost, "results": results}, f, indent=2)
    print(f"✅ Resultados salvos em backend/scripts/sprint03_results.json")


if __name__ == "__main__":
    token = get_token()
    run_pipeline(token)
