"""Cliente de Supabase perezoso.

Se crea recién en el primer uso: así el módulo se puede importar (y los
tests correr) sin credenciales, y el error —si faltan— aparece cuando de
verdad se necesita la DB, con un mensaje claro.
"""

from typing import Any

from app.config import SUPABASE_SECRET_KEY, SUPABASE_URL

_client: Any | None = None


def get_client() -> Any:
    global _client

    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
            raise RuntimeError(
                "Faltan SUPABASE_URL o SUPABASE_SECRET_KEY en el entorno (.env)."
            )
        from supabase import create_client

        _client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

    return _client


def set_client(client: Any) -> None:
    """Inyecta un cliente (lo usan los tests)."""
    global _client
    _client = client


class _LazySupabase:
    """Proxy: `supabase.table(...)` sigue funcionando igual que antes."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_client(), name)


supabase = _LazySupabase()
