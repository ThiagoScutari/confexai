import os
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/examples/uploads"))


def path_to_url(file_path: str | Path) -> str:
    """
    Converte path absoluto do container para URL relativa do static serving.
    Ex: /app/examples/uploads/uuid/color_696980_frente.jpg
     ->  /static/uploads/uuid/color_696980_frente.jpg
    """
    path = Path(file_path)
    try:
        relative = path.relative_to(UPLOAD_DIR)
        return f"/static/uploads/{relative}"
    except ValueError:
        # Path fora do UPLOAD_DIR — retornar como esta
        return str(file_path)
