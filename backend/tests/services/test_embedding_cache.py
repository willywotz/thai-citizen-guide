import app.services.embedding as emb


class FakeResp:
    status_code = 200

    def json(self):
        return {"data": [{"embedding": [0.1] * 384}]}


class FakeRespB:
    status_code = 200

    def json(self):
        return {"data": [{"embedding": [0.9] * 384}]}


async def test_identical_text_hits_cache(monkeypatch):
    emb._cache_clear()
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k): ...

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a): ...

        async def post(self, *a, **k):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(emb.settings, "EMBEDDING_API_KEY", "x")
    monkeypatch.setattr(emb.httpx, "AsyncClient", FakeClient)
    a = await emb.generate_embedding("same text")
    b = await emb.generate_embedding("same text")
    assert a == b
    assert calls["n"] == 1  # second call served from cache


async def test_different_texts_are_not_confused(monkeypatch):
    emb._cache_clear()
    call_count = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k): ...

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a): ...

        async def post(self, *a, **k):
            call_count["n"] += 1
            # return different embeddings based on call order so we can verify keying
            if call_count["n"] == 1:
                return FakeResp()
            return FakeRespB()

    monkeypatch.setattr(emb.settings, "EMBEDDING_API_KEY", "x")
    monkeypatch.setattr(emb.httpx, "AsyncClient", FakeClient)
    a = await emb.generate_embedding("text A")
    b = await emb.generate_embedding("text B")
    assert a != b  # cache must not confuse different keys
    assert call_count["n"] == 2  # both triggered a network call


async def test_cache_clear_causes_new_network_call(monkeypatch):
    emb._cache_clear()
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k): ...

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a): ...

        async def post(self, *a, **k):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(emb.settings, "EMBEDDING_API_KEY", "x")
    monkeypatch.setattr(emb.httpx, "AsyncClient", FakeClient)
    await emb.generate_embedding("hello")
    assert calls["n"] == 1
    emb._cache_clear()
    await emb.generate_embedding("hello")
    assert calls["n"] == 2  # cache was cleared so a new call was made


async def test_mutating_returned_vector_does_not_corrupt_cache(monkeypatch):
    """Mutating the list returned by generate_embedding must not corrupt the cache."""
    emb._cache_clear()
    calls = {"n": 0}
    original = [0.1] * 384

    class FakeClient:
        def __init__(self, *a, **k): ...

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a): ...

        async def post(self, *a, **k):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(emb.settings, "EMBEDDING_API_KEY", "x")
    monkeypatch.setattr(emb.httpx, "AsyncClient", FakeClient)

    first = await emb.generate_embedding("mutation test")
    assert first == original
    first[0] = 999.0  # mutate the returned list

    second = await emb.generate_embedding("mutation test")
    assert calls["n"] == 1  # no new network call — served from cache
    assert second[0] == 0.1  # cache was not corrupted by the mutation
    assert second == original


async def test_cache_entry_expires_after_ttl(monkeypatch):
    """Entries older than TTL are evicted and trigger a fresh network call."""
    emb._cache_clear()
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k): ...

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a): ...

        async def post(self, *a, **k):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(emb.settings, "EMBEDDING_API_KEY", "x")
    monkeypatch.setattr(emb.httpx, "AsyncClient", FakeClient)

    # Seed the cache with a very stale timestamp
    import time

    key = (emb.settings.EMBEDDING_MODEL, emb.settings.EMBEDDING_DIMENSIONS, "stale text")
    emb._embedding_cache[key] = ([0.1] * 384, time.monotonic() - emb._CACHE_TTL_SECONDS - 1)

    result = await emb.generate_embedding("stale text")
    assert result is not None
    assert calls["n"] == 1  # stale entry was evicted, new call made
