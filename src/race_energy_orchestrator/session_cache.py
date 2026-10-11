from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Callable


SessionKey = tuple[int, str, str, str]
Session = dict[str, object]


@dataclass(frozen=True)
class _Entry:
    result: Future[Session]
    expires_at: float


class SessionCache:
    """Bounded process-local cache sharing one active load per session key."""

    def __init__(
        self,
        maxsize: int = 16,
        ttl_s: float = 1800.0,
        failure_ttl_s: float = 30.0,
        cache_error: Callable[[Exception], bool] = lambda error: False,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if maxsize < 1 or ttl_s <= 0 or failure_ttl_s < 0:
            raise ValueError("Cache size and TTL must be positive; failure TTL may be zero.")
        self._maxsize = maxsize
        self._ttl_s = ttl_s
        self._failure_ttl_s = failure_ttl_s
        self._cache_error = cache_error
        self._clock = clock
        self._lock = RLock()
        self._entries: OrderedDict[SessionKey, _Entry] = OrderedDict()
        self._inflight: dict[SessionKey, Future[Session]] = {}

    def get(self, key: SessionKey, load: Callable[[], Session]) -> Session:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at <= self._clock():
                del self._entries[key]
                entry = None
            if entry is not None:
                self._entries.move_to_end(key)
                result = entry.result
                owner = False
            else:
                result = self._inflight.get(key)
                owner = result is None
                if result is None:
                    result = Future()
                    self._inflight[key] = result

        if not owner:
            return result.result()

        # Expensive loading and waiting never hold the shared cache lock.
        try:
            value = load()
        except BaseException as error:
            ttl = self._failure_ttl_s if isinstance(error, Exception) and self._cache_error(error) else 0.0
            self._finish(key, result, ttl)
            result.set_exception(error)
            raise
        self._finish(key, result, self._ttl_s)
        result.set_result(value)
        return value

    def _finish(self, key: SessionKey, result: Future[Session], ttl_s: float) -> None:
        with self._lock:
            # A clear during loading must not repopulate the cache with the old result.
            if self._inflight.get(key) is not result:
                return
            del self._inflight[key]
            if ttl_s <= 0:
                return
            now = self._clock()
            for expired in [key for key, entry in self._entries.items() if entry.expires_at <= now]:
                del self._entries[expired]
            self._entries[key] = _Entry(result, now + ttl_s)
            while len(self._entries) > self._maxsize:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._inflight.clear()
