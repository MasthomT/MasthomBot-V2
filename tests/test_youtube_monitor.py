"""Flux RSS YouTube : un 404 passager est réessayé dans le même cycle."""

import asyncio

import pytest

from app.services import youtube_monitor


def _fake_session(statuses):
    calls = {"n": 0}

    class _Resp:
        def __init__(self, status):
            self.status = status

        async def text(self):
            return "<feed/>"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _Session:
        def __init__(self, *a, **k):
            pass

        def get(self, *a, **k):
            status = statuses[min(calls["n"], len(statuses) - 1)]
            calls["n"] += 1
            return _Resp(status)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    return _Session, calls


def test_transient_404_is_retried(monkeypatch):
    session, calls = _fake_session([404, 404, 200])
    monkeypatch.setattr(youtube_monitor.aiohttp, "ClientSession", session)
    monkeypatch.setattr(youtube_monitor, "FETCH_RETRY_DELAY", 0)
    assert asyncio.run(youtube_monitor._fetch_feed("UCx")) == "<feed/>"
    assert calls["n"] == 3


def test_persistent_404_raises_after_all_attempts(monkeypatch):
    session, calls = _fake_session([404])
    monkeypatch.setattr(youtube_monitor.aiohttp, "ClientSession", session)
    monkeypatch.setattr(youtube_monitor, "FETCH_RETRY_DELAY", 0)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        asyncio.run(youtube_monitor._fetch_feed("UCx"))
    assert calls["n"] == youtube_monitor.FETCH_ATTEMPTS
