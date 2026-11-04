from supabase import Client, ClientOptions, create_client

from app.config import SUPABASE_SECRET_KEY, SUPABASE_URL

STORAGE_TIMEOUT_SECONDS = 120

_client: Client | None = None


class _SupabaseProxy:
    """Crea el cliente real recién en el primer uso.

    Evita que el proceso entero crashee al importar si faltan las env vars
    (SUPABASE_URL / SUPABASE_SECRET_KEY); en su lugar, el error aparece
    recién cuando un endpoint efectivamente necesita Supabase.
    """

    def _get(self) -> Client:
        global _client
        if _client is None:
            if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
                raise RuntimeError(
                    "Faltan las variables de entorno SUPABASE_URL / SUPABASE_SECRET_KEY"
                )
            _client = create_client(
                SUPABASE_URL,
                SUPABASE_SECRET_KEY,
                # Storage por defecto corta a los 20 s: subir/bajar STL de varios MB
                # desde Render no siempre llega ("The read operation timed out").
                options=ClientOptions(storage_client_timeout=STORAGE_TIMEOUT_SECONDS),
            )
        return _client

    def __getattr__(self, name):
        return getattr(self._get(), name)


supabase = _SupabaseProxy()
