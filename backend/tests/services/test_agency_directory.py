import time

import pytest

from app.models import Agency
from app.services import agency_directory


@pytest.mark.usefixtures("db")
async def test_snapshot_caches_and_invalidates():
    await Agency.create(name="A", status="active")
    agency_directory.invalidate()
    first = await agency_directory.snapshot()
    assert len(first) == 1
    await Agency.create(name="B", status="active")
    cached = await agency_directory.snapshot()
    assert len(cached) == 1          # still cached
    agency_directory.invalidate()
    fresh = await agency_directory.snapshot()
    assert len(fresh) == 2


@pytest.mark.usefixtures("db")
async def test_snapshot_excludes_inactive():
    await Agency.create(name="Active", status="active")
    await Agency.create(name="Draft", status="draft")
    await Agency.create(name="Disabled", status="disabled")
    agency_directory.invalidate()
    result = await agency_directory.snapshot()
    names = [a["name"] for a in result]
    assert "Active" in names
    assert "Draft" not in names
    assert "Disabled" not in names


@pytest.mark.usefixtures("db")
async def test_snapshot_refetches_after_ttl_expires(monkeypatch):
    """Cache should re-query after TTL elapses, not before."""
    await Agency.create(name="A", status="active")
    agency_directory.invalidate()

    # Prime the cache.
    first = await agency_directory.snapshot()
    assert len(first) == 1

    # Add a second agency without invalidating.
    await Agency.create(name="B", status="active")

    # Within TTL: still one result from cache.
    within = await agency_directory.snapshot()
    assert len(within) == 1

    # Simulate TTL elapsed by fast-forwarding monotonic time.
    real_monotonic = time.monotonic
    monkeypatch.setattr(
        "app.services.agency_directory.time",
        type("_t", (), {"monotonic": staticmethod(lambda: real_monotonic() + agency_directory._CACHE_TTL_S + 1)})(),
    )

    # After TTL: fresh query returns both agencies.
    after_ttl = await agency_directory.snapshot()
    assert len(after_ttl) == 2


def test_prefilter_matches_by_name():
    agencies = [
        {"name": "กรมสรรพากร", "data_scope": ["ภาษี", "VAT"]},
        {"name": "กรมขนส่ง", "data_scope": ["รถยนต์", "ทะเบียน"]},
        {"name": "กรมที่ดิน", "data_scope": ["โฉนด", "ที่ดิน"]},
    ]
    result = agency_directory.prefilter(agencies, "ภาษีรถยนต์ กรมสรรพากร")
    names = [a["name"] for a in result]
    assert "กรมสรรพากร" in names
    assert "กรมขนส่ง" in names


def test_prefilter_falls_back_to_all_when_too_few_matches():
    agencies = [
        {"name": "Agency A", "data_scope": ["tax"]},
        {"name": "Agency B", "data_scope": ["transport"]},
        {"name": "Agency C", "data_scope": ["land"]},
    ]
    # Query only matches 1 agency → fewer than 3 → fall back to all
    result = agency_directory.prefilter(agencies, "tax")
    assert len(result) == 3


def test_prefilter_empty_query_returns_all():
    agencies = [{"name": f"Agency {i}", "data_scope": []} for i in range(5)]
    result = agency_directory.prefilter(agencies, "")
    assert len(result) == 5


def test_prefilter_caps_at_max_n():
    agencies = [{"name": f"Agency {i}", "data_scope": []} for i in range(30)]
    result = agency_directory.prefilter(agencies, "", max_n=10)
    assert len(result) == 10


def test_prefilter_returns_matching_when_3_or_more_match():
    agencies = [
        {"name": "Land Office", "data_scope": ["ที่ดิน", "โฉนด"]},
        {"name": "Land Registry", "data_scope": ["ที่ดิน", "สิทธิ์"]},
        {"name": "Land Survey", "data_scope": ["ที่ดิน", "แผนที่"]},
        {"name": "Tax Dept", "data_scope": ["ภาษี"]},
    ]
    result = agency_directory.prefilter(agencies, "ที่ดิน")
    names = [a["name"] for a in result]
    # 3 matches → returns only matching (not fallback to all 4)
    assert len(result) == 3
    assert "Tax Dept" not in names
