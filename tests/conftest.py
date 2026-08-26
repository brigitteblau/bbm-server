"""Supabase falso: los tests e2e corren sin credenciales ni red."""

import uuid

import pytest

from app import supabase_client


class FakeQuery:
    def __init__(self, table: "FakeTable"):
        self.table = table
        self._filters: dict[str, str] = {}
        self._single = False
        self._pending_insert: dict | None = None

    # ── escritura ────────────────────────────────────────────────────────
    def insert(self, record: dict):
        self._pending_insert = record
        return self

    # ── lectura ──────────────────────────────────────────────────────────
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value):
        self._filters[column] = str(value)
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        if self.table.raise_on_execute:
            raise RuntimeError(self.table.raise_on_execute)

        if self._pending_insert is not None:
            row = dict(self._pending_insert)
            row.setdefault("id", str(uuid.uuid4()))
            self.table.rows.append(row)
            return FakeResponse([row])

        rows = [
            row
            for row in self.table.rows
            if all(str(row.get(k)) == v for k, v in self._filters.items())
        ]

        if self._single:
            if not rows:
                raise RuntimeError("no rows returned")
            return FakeResponse(rows[0])

        return FakeResponse(rows)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self):
        self.rows: list[dict] = []
        self.raise_on_execute: str | None = None

    def _query(self):
        return FakeQuery(self)


class FakeBucket:
    def __init__(self, name: str):
        self.name = name
        self.files: dict[str, bytes] = {}

    def upload(self, path: str, data: bytes, options: dict | None = None):
        if path in self.files:
            raise RuntimeError(f"'{path}' ya existe en el bucket")
        self.files[path] = data
        return {"path": path}

    def download(self, path: str) -> bytes:
        if path not in self.files:
            raise RuntimeError(f"'{path}' no existe en el bucket")
        return self.files[path]

    def create_signed_url(self, path: str, expires_in: int):
        if path not in self.files:
            raise RuntimeError(f"'{path}' no existe en el bucket")
        return {"signedURL": f"https://fake.supabase/{self.name}/{path}?exp={expires_in}"}


class FakeStorage:
    def __init__(self):
        self.buckets: dict[str, FakeBucket] = {}

    def from_(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket(name))


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, FakeTable] = {}
        self.storage = FakeStorage()

    def table(self, name: str):
        return self.tables.setdefault(name, FakeTable())._query()

    # helpers para los tests
    def rows(self, name: str) -> list[dict]:
        return self.tables.setdefault(name, FakeTable()).rows

    def fail_table(self, name: str, message: str) -> None:
        self.tables.setdefault(name, FakeTable()).raise_on_execute = message


@pytest.fixture(autouse=True)
def blender_apagado(monkeypatch):
    """Los tests no dependen de tener bpy instalado en la máquina."""
    monkeypatch.setenv("BLENDER_ENABLED", "false")


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase()
    supabase_client.set_client(fake)
    yield fake
    supabase_client.set_client(None)
