from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _AsyncCM:
    """Stand-in for `async with in_transaction() as conn`."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


def _make_query_mock(count_values=None, values_values=None):
    """Chainable Tortoise queryset mock.

    filter/annotate/group_by return self; count/values pop from the provided lists.
    """
    m = MagicMock()
    m.filter.return_value = m
    m.annotate.return_value = m
    m.group_by.return_value = m
    m.count = AsyncMock(side_effect=list(count_values or []))
    m.values = AsyncMock(side_effect=list(values_values or []))
    return m


@pytest.mark.asyncio
async def test_get_dashboard_stats_shape():
    from app.services import analytics

    conn = MagicMock()
    conn.execute_query = AsyncMock()
    conn.execute_query_dict = AsyncMock(return_value=[{"dow": 1, "questions": 4}])

    # Call order in get_dashboard_stats:
    # count x2: totalQuestions, todayQuestions
    # values x3: avg_time, rate, categories
    msg = _make_query_mock(
        count_values=[5, 2],
        values_values=[
            [{"avg_time": 1500}],
            [{"rate": 80}],
            [{"category": "x", "cnt": 3}],
        ],
    )
    agency = MagicMock()
    agency.all.return_value = MagicMock(
        values=AsyncMock(return_value=[{"name": "A", "color": "#fff", "total_calls": 10}])
    )

    with (
        patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)),
        patch.object(analytics, "Message", msg),
        patch.object(analytics, "Agency", agency),
    ):
        result = await analytics.get_dashboard_stats()

    assert set(result.keys()) == {"stats", "agencyUsage", "weeklyTrend", "categoryData"}
    assert len(result["weeklyTrend"]) == 7
    assert result["stats"]["totalQuestions"] == 5
    assert result["stats"]["todayQuestions"] == 2
    assert result["agencyUsage"] == [{"name": "A", "value": 10, "fill": "#fff"}]
    assert result["categoryData"] == [{"category": "x", "count": 3}]


@pytest.mark.asyncio
async def test_get_agency_health_empty_agencies():
    from app.schemas.insight import AgencyHealthData
    from app.services import analytics

    conn = MagicMock()
    conn.execute_query = AsyncMock()

    agency = MagicMock()
    agency.all.return_value = MagicMock(values=AsyncMock(return_value=[]))

    # ConnectionLog is used after the (empty) loop for rawHistorical query:
    # ConnectionLog.annotate(...).filter(...).group_by(...).values(...) -> []
    conn_log = MagicMock()
    conn_log.annotate.return_value = conn_log
    conn_log.filter.return_value = conn_log
    conn_log.group_by.return_value = conn_log
    conn_log.values = AsyncMock(return_value=[])

    with (
        patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)),
        patch.object(analytics, "Agency", agency),
        patch.object(analytics, "ConnectionLog", conn_log),
    ):
        result = await analytics.get_agency_health()

    assert isinstance(result, AgencyHealthData)
    assert result.agencies == []
    assert result.historical == []


@pytest.mark.asyncio
async def test_get_executive_summary_smoke():
    from app.schemas.executive_summary import ExecutiveData
    from app.services import analytics

    conn = MagicMock()
    conn.execute_query = AsyncMock()

    # Message.filter(...).count() is called 4 times (thisMonth, lastMonth, thisYear, lastYear).
    # Message.annotate(...).filter(...).group_by(...).annotate(...)x3.values(...) once (monthlyTrend).
    # Using fixed return_value=0 / [] so call order doesn't matter.
    msg = MagicMock()
    msg.filter.return_value = msg
    msg.annotate.return_value = msg
    msg.group_by.return_value = msg
    msg.count = AsyncMock(return_value=0)
    msg.values = AsyncMock(return_value=[])

    # Conversation.filter(...).count() called 4 times.
    conv = MagicMock()
    conv.filter.return_value = conv
    conv.count = AsyncMock(return_value=0)

    with (
        patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)),
        patch.object(analytics, "Message", msg),
        patch.object(analytics, "Conversation", conv),
        patch.object(analytics, "_get_weekly_brief", new=AsyncMock(return_value="brief")),
    ):
        result = await analytics.get_executive_summary()

    assert isinstance(result, ExecutiveData)
    assert result.weeklyBrief == "brief"


@pytest.mark.asyncio
async def test_get_weekly_brief_returns_fallback_on_http_error(monkeypatch):
    """When the httpx call raises, _get_weekly_brief must return the Thai fallback string."""
    from app.services import analytics

    # Reset the module-level cache so the function actually makes an HTTP call.
    monkeypatch.setattr(analytics, "_weekly_brief_cache", "")

    class _RaisingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("network error")

    with patch("app.services.analytics.httpx.AsyncClient", return_value=_RaisingClient()):
        result = await analytics._get_weekly_brief("some content")

    assert result == "ไม่สามารถสร้างสรุปประจำสัปดาห์ได้ในขณะนี้"


@pytest.mark.asyncio
async def test_get_executive_summary_january_month_boundary():
    """prev_month must be 12 in January, not 0."""
    from app.services import analytics
    from unittest.mock import patch as _patch
    from app.utils import now as _now
    import datetime

    # Freeze time to January 15.
    jan_15 = datetime.datetime(2026, 1, 15, tzinfo=datetime.timezone.utc)

    conn = MagicMock()
    conn.execute_query = AsyncMock()

    msg = MagicMock()
    msg.filter.return_value = msg
    msg.annotate.return_value = msg
    msg.group_by.return_value = msg
    msg.count = AsyncMock(return_value=0)
    msg.values = AsyncMock(return_value=[])

    conv = MagicMock()
    conv.filter.return_value = conv
    conv.count = AsyncMock(return_value=0)

    # Capture the month keyword arg passed to Message.filter for lastMonthQuestions.
    captured_months = []
    original_filter = msg.filter

    def _capturing_filter(**kwargs):
        if "created_at__month" in kwargs:
            captured_months.append(kwargs["created_at__month"])
        return msg

    msg.filter.side_effect = _capturing_filter

    with (
        _patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)),
        _patch.object(analytics, "Message", msg),
        _patch.object(analytics, "Conversation", conv),
        _patch.object(analytics, "_get_weekly_brief", new=AsyncMock(return_value="brief")),
        _patch("app.services.analytics.now", return_value=jan_15),
    ):
        await analytics.get_executive_summary()

    # All captured month values must be valid (1-12); 0 must never appear.
    assert 0 not in captured_months, f"Invalid month 0 found in filter calls: {captured_months}"
    assert 12 in captured_months, f"Expected December (12) for prev_month in January, got: {captured_months}"
