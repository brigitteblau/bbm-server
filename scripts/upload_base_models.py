"""Sube los STL base al bucket base-models (pisa los existentes, con backup local).

Uso: python -m scripts.upload_base_models <carpeta con proto.stl y default_back.stl>
Requiere SUPABASE_URL y SUPABASE_SECRET_KEY en .env.
"""

import sys
from pathlib import Path

from app.services.generators.trimesh_scaler import (
    BASE_MODELS_BUCKET,
    DEFAULT_STL_BY_POSITION,
)
from app.supabase_client import supabase


def main(folder: Path) -> None:
    bucket = supabase.storage.from_(BASE_MODELS_BUCKET)
    backup_dir = folder / "backup"
    backup_dir.mkdir(exist_ok=True)

    for name in DEFAULT_STL_BY_POSITION.values():
        try:
            (backup_dir / name).write_bytes(bucket.download(name))
            print(f"backup: {name}")
        except Exception:
            print(f"sin versión previa: {name}")

        data = (folder / name).read_bytes()
        bucket.upload(name, data, {"content-type": "model/stl", "upsert": "true"})
        print(f"subido: {name} ({len(data) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
