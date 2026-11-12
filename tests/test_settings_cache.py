"""Cache des réglages : une seule lecture en base tant que le cache est valide,
relecture après invalidation ou expiration, et copies indépendantes."""

import asyncio
import contextlib

import pytest

from app.core import settings_cache


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, store, calls):
        self.store, self.calls = store, calls

    async def execute(self, sql, *params):
        table = "personality" if "personality" in sql else "settings"
        self.calls.append(table)
        return _FakeCursor(dict(self.store[table]))


@pytest.fixture
def fake_db(monkeypatch):
    store = {"settings": {"id": 1, "ai_enabled": 1, "personal_last_live_id": ""},
             "personality": {"id": 1, "system_prompt": "Tu es Félix."}}
    calls = []

    @contextlib.asynccontextmanager
    async def _conn():
        yield _FakeConn(store, calls)

    monkeypatch.setattr(settings_cache, "get_db_connection", _conn)
    settings_cache.invalidate_settings()
    yield store, calls
    settings_cache.invalidate_settings()


def test_reads_db_once_while_cached(fake_db):
    store, calls = fake_db

    async def scenario():
        for _ in range(50):
            await settings_cache.get_settings()
    asyncio.run(scenario())
    assert calls.count("settings") == 1


def test_invalidate_forces_reload(fake_db):
    store, calls = fake_db

    async def scenario():
        assert await settings_cache.is_live() is False
        store["settings"]["personal_last_live_id"] = "123"
        assert await settings_cache.is_live() is False      # encore en cache
        settings_cache.invalidate_settings()
        assert await settings_cache.is_live() is True       # relu après invalidation
        assert await settings_cache.current_live_id() == "123"
    asyncio.run(scenario())


def test_expires_after_ttl(fake_db, monkeypatch):
    store, calls = fake_db
    monkeypatch.setattr(settings_cache, "CACHE_TTL", 0)

    async def scenario():
        await settings_cache.get_settings()
        await settings_cache.get_settings()
    asyncio.run(scenario())
    assert calls.count("settings") == 2


def test_returned_dict_is_a_copy(fake_db):
    async def scenario():
        s = await settings_cache.get_settings()
        s["ai_enabled"] = 0
        assert (await settings_cache.get_settings())["ai_enabled"] == 1
    asyncio.run(scenario())


def test_personality_cached_separately(fake_db):
    store, calls = fake_db

    async def scenario():
        assert (await settings_cache.get_personality())["system_prompt"] == "Tu es Félix."
        await settings_cache.get_personality()
    asyncio.run(scenario())
    assert calls.count("personality") == 1
