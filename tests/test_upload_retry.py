"""La subida del STL reintenta si Supabase se corta (bug: 'The read operation timed out')."""
import pytest

from app.routes import prosthesis


class FakeBucket:
    def __init__(self, fallas: int):
        self.fallas = fallas
        self.llamadas = []

    def upload(self, filename, data, options):
        self.llamadas.append(options["upsert"])
        if len(self.llamadas) <= self.fallas:
            raise TimeoutError("The read operation timed out")


class FakeSupabase:
    def __init__(self, bucket):
        self.storage = self
        self.bucket = bucket

    def from_(self, _name):
        return self.bucket


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(prosthesis.time, "sleep", lambda _s: None)


def test_reintenta_y_sube(monkeypatch):
    bucket = FakeBucket(fallas=2)
    monkeypatch.setattr(prosthesis, "supabase", FakeSupabase(bucket))
    prosthesis._upload_stl("perro.stl", b"stl")
    # primer intento sin upsert, los reintentos con upsert (por si el anterior llegó a escribir)
    assert bucket.llamadas == ["false", "true", "true"]


def test_si_falla_siempre_propaga_el_error(monkeypatch):
    monkeypatch.setattr(prosthesis, "supabase", FakeSupabase(FakeBucket(fallas=99)))
    with pytest.raises(TimeoutError):
        prosthesis._upload_stl("perro.stl", b"stl")


def test_cliente_usa_timeout_largo(monkeypatch):
    from app import supabase_client

    capturado = {}
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(supabase_client, "SUPABASE_SECRET_KEY", "clave")
    monkeypatch.setattr(supabase_client, "_client", None)
    monkeypatch.setattr(supabase_client, "create_client",
                        lambda url, key, options: capturado.setdefault("o", options))
    supabase_client.supabase._get()
    assert capturado["o"].storage_client_timeout == supabase_client.STORAGE_TIMEOUT_SECONDS == 120


def test_blender_prendido_por_defecto(monkeypatch):
    from app.services.generators import selector

    monkeypatch.delenv("BLENDER_ENABLED", raising=False)
    assert selector._blender_enabled() is True
    monkeypatch.setenv("BLENDER_ENABLED", "false")
    assert selector._blender_enabled() is False
