from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock

import pytest
from fastapi.testclient import TestClient

from race_energy_orchestrator import api, session_cache
from race_energy_orchestrator.data import FastF1DataUnavailable
from race_energy_orchestrator.session_cache import SessionCache


SUZUKA = (2026, "Suzuka", "Q", "LEC")
MONZA = (2026, "Monza", "Q", "LEC")


@pytest.mark.parametrize("fails", [False, True])
def test_concurrent_requests_share_one_load_and_outcome(monkeypatch, fails):
    started, release, followers_waiting = Event(), Event(), Event()
    lock = Lock()
    calls = 0
    waiters = 0
    value = {"event": "Suzuka"}

    class ObservedFuture(Future):
        def result(self, timeout=None):
            nonlocal waiters
            if not self.done():
                with lock:
                    waiters += 1
                    if waiters == 7:
                        followers_waiting.set()
            return super().result(timeout)

    monkeypatch.setattr(session_cache, "Future", ObservedFuture)
    cache = SessionCache()

    def load():
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(5)
        if fails:
            raise RuntimeError("load failed")
        return value

    with ThreadPoolExecutor(max_workers=8) as pool:
        leader = pool.submit(cache.get, SUZUKA, load)
        try:
            assert started.wait(2)
            followers = [pool.submit(cache.get, SUZUKA, load) for _ in range(7)]
            assert followers_waiting.wait(2)
        finally:
            release.set()
        for request in [leader, *followers]:
            if fails:
                with pytest.raises(RuntimeError, match="load failed"):
                    request.result(timeout=2)
            else:
                assert request.result(timeout=2) is value
    assert calls == 1


def test_slow_session_does_not_block_cached_session():
    cache = SessionCache()
    warm = cache.get(SUZUKA, lambda: {"event": "Suzuka"})
    started, release = Event(), Event()

    def slow_load():
        started.set()
        assert release.wait(5)
        return {"event": "Monza"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        cold = pool.submit(cache.get, MONZA, slow_load)
        try:
            assert started.wait(2)
            ready = pool.submit(cache.get, SUZUKA, lambda: pytest.fail("cache missed"))
            assert ready.result(timeout=1) is warm
            assert not cold.done()
        finally:
            release.set()
        assert cold.result(timeout=2)["event"] == "Monza"


def test_different_sessions_can_load_concurrently():
    cache = SessionCache()
    started = [Event(), Event()]
    release = Event()

    def load(index):
        started[index].set()
        assert release.wait(5)
        return {"index": index}

    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(cache.get, key, lambda i=i: load(i)) for i, key in enumerate([SUZUKA, MONZA])]
        try:
            assert all(event.wait(2) for event in started)
        finally:
            release.set()
        assert [request.result(timeout=2)["index"] for request in requests] == [0, 1]


def test_session_expires_from_completion_time():
    now = [0.0]
    cache = SessionCache(ttl_s=10, clock=lambda: now[0])
    calls = 0

    def load():
        nonlocal calls
        calls += 1
        now[0] += 5
        return {"load": calls}

    first = cache.get(SUZUKA, load)
    now[0] = 14.9
    assert cache.get(SUZUKA, load) is first
    now[0] = 15.0
    assert cache.get(SUZUKA, load)["load"] == 2


def test_least_recently_used_session_is_evicted():
    cache = SessionCache(maxsize=2)
    first = cache.get(SUZUKA, lambda: {"event": "Suzuka"})
    cache.get(MONZA, lambda: {"event": "Monza"})
    assert cache.get(SUZUKA, lambda: pytest.fail("cache missed")) is first
    cache.get((2026, "Monaco", "Q", "LEC"), lambda: {"event": "Monaco"})
    assert cache.get(SUZUKA, lambda: pytest.fail("cache missed")) is first
    assert cache.get(MONZA, lambda: {"reloaded": True}) == {"reloaded": True}


def test_failure_cooldown_expires_and_allows_recovery():
    now = [0.0]
    cache = SessionCache(failure_ttl_s=30, cache_error=lambda error: isinstance(error, FastF1DataUnavailable), clock=lambda: now[0])
    calls = 0

    def load():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise FastF1DataUnavailable("no telemetry")
        return {"event": "Suzuka"}

    for when in [0.0, 29.9]:
        now[0] = when
        with pytest.raises(FastF1DataUnavailable, match="no telemetry"):
            cache.get(SUZUKA, load)
    assert calls == 1
    now[0] = 30.0
    assert cache.get(SUZUKA, load) == {"event": "Suzuka"}
    assert calls == 2


def test_unexpected_error_is_not_cached():
    cache = SessionCache(cache_error=lambda error: isinstance(error, FastF1DataUnavailable))
    calls = 0

    def load():
        nonlocal calls
        calls += 1
        raise ValueError("model error")

    for _ in range(2):
        with pytest.raises(ValueError, match="model error"):
            cache.get(SUZUKA, load)
    assert calls == 2


def test_clear_during_load_does_not_restore_old_result():
    cache = SessionCache()
    started, release = Event(), Event()

    def old_load():
        started.set()
        assert release.wait(5)
        return {"version": "old"}

    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(cache.get, SUZUKA, old_load)
        try:
            assert started.wait(2)
            cache.clear()
            fresh = cache.get(SUZUKA, lambda: {"version": "fresh"})
        finally:
            release.set()
        assert old.result(timeout=2) == {"version": "old"}
    assert cache.get(SUZUKA, lambda: pytest.fail("cache missed")) is fresh


def test_api_normalizes_session_key(monkeypatch):
    calls = []

    def load(*key):
        calls.append(key)
        return {"event": key[1]}

    monkeypatch.setattr(api, "_build_session", load)
    monkeypatch.setattr(api, "_SESSION_CACHE", SessionCache())
    first = api._session(2026, " Suzuka ", " q ", " lec ")
    assert api._session(*SUZUKA) is first
    assert calls == [SUZUKA]


def test_api_unavailable_source_shares_cooldown_across_endpoints(monkeypatch):
    calls = 0

    def unavailable_loader(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["synthetic_only"] is False
        assert kwargs["allow_synthetic_fallback"] is False
        raise FastF1DataUnavailable("no telemetry")

    monkeypatch.setattr(api, "load_lap_data", unavailable_loader)
    monkeypatch.setattr(api, "_SESSION_CACHE", SessionCache(cache_error=lambda error: getattr(error, "status_code", None) == 503))
    client = TestClient(api.app)
    for path in ["/api/session", "/api/metrics", "/api/decision", "/api/trace"]:
        response = client.get(path)
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "30"
        assert response.json()["detail"] == "no telemetry"
    assert calls == 1
