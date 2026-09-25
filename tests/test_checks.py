import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app import checks
from app.ai import Extraction, ExtractionError
from app.database import utcnow
from app.models import Item, NotificationProfile, PriceHistory
from app.scraper import Capture, ScrapeError
from app.settings import AppSettings


def make_item(**fields) -> Item:
    defaults = {"id": 1, "url": "https://example.com", "name": "Widget", "current_price": 100.0, "in_stock": True}
    return Item(**defaults | fields)


def extraction(price=100.0, in_stock=True, price_confidence=0.9, in_stock_confidence=0.9) -> Extraction:
    return Extraction(
        price=price, in_stock=in_stock, price_confidence=price_confidence, in_stock_confidence=in_stock_confidence
    )


# apply_extraction


def test_accepted_price_updates_item_and_returns_history():
    item = make_item(consecutive_failures=3, last_error="old", error_type="scrape_failed")
    history = checks.apply_extraction(item, extraction(price=90.0, in_stock=False), AppSettings())

    assert (item.current_price, item.in_stock, item.consecutive_failures) == (90.0, False, 0)
    assert item.last_error is None and item.error_type is None
    assert item.last_checked is not None
    assert (history.price, history.in_stock, history.ai_model) == (90.0, False, "gemma3:4b")


def test_low_confidence_price_is_recorded_but_not_applied():
    item = make_item()
    history = checks.apply_extraction(item, extraction(price=80.0, price_confidence=0.3), AppSettings())

    assert item.current_price == 100.0
    assert item.error_type == "low_confidence"
    assert "30% confidence" in item.last_error
    assert history.price == 80.0


def test_large_change_with_middling_confidence_is_applied_but_flagged():
    item = make_item()
    checks.apply_extraction(item, extraction(price=150.0, price_confidence=0.6), AppSettings())

    assert item.current_price == 150.0
    assert item.error_type == "low_confidence"
    assert "please verify" in item.last_error


@pytest.mark.parametrize("price", [250.0, 20.0])
def test_outliers_are_rejected_in_both_directions(price):
    item = make_item()
    settings = AppSettings(price_outlier_threshold_enabled=True, price_outlier_threshold_percent=50)
    history = checks.apply_extraction(item, extraction(price=price, in_stock=False), settings)

    assert history is None
    assert item.current_price == 100.0
    assert item.in_stock is True  # nothing from a rejected extraction is applied
    assert item.error_type == "outlier_rejected"


def test_outlier_check_is_off_by_default():
    item = make_item()
    checks.apply_extraction(item, extraction(price=250.0), AppSettings())
    assert item.current_price == 250.0


@pytest.mark.parametrize("price", [0.001, 200_000.0])
def test_prices_outside_sanity_bounds_are_rejected(price):
    item = make_item()
    assert checks.apply_extraction(item, extraction(price=price), AppSettings()) is None
    assert item.error_type == "price_out_of_bounds"


def test_missing_price_warns():
    item = make_item()
    history = checks.apply_extraction(item, extraction(price=None, in_stock=True), AppSettings())

    assert history is None
    assert item.error_type == "no_price"


def test_sold_out_page_without_price_is_not_a_warning():
    item = make_item()
    checks.apply_extraction(item, extraction(price=None, in_stock=False), AppSettings())
    assert item.last_error is None


def test_low_confidence_stock_is_ignored():
    item = make_item()
    checks.apply_extraction(item, extraction(in_stock=False, in_stock_confidence=0.2), AppSettings())
    assert item.in_stock is True


# Claims and scheduling


async def test_claim_is_exclusive_until_stale(db):
    item = Item(url="https://example.com", name="Widget")
    db.add(item)
    await db.commit()

    assert await checks.claim(db, [item.id]) == [item.id]
    assert await checks.claim(db, [item.id]) == []

    item.refresh_started_at = utcnow() - checks.CLAIM_TIMEOUT - timedelta(minutes=1)
    await db.commit()
    assert await checks.claim(db, [item.id]) == [item.id]


async def test_claim_skips_paused_items_unless_asked(db):
    item = Item(url="https://example.com", name="Paused", is_active=False)
    db.add(item)
    await db.commit()

    assert await checks.claim(db) == []
    assert await checks.claim(db, [item.id], active_only=False) == [item.id]


async def test_claim_due_respects_item_profile_and_global_intervals(db):
    now = utcnow()
    profile = NotificationProfile(name="Hourly", apprise_url="json://localhost", check_interval_minutes=60)
    db.add(profile)
    await db.flush()
    never = Item(url="https://a.com", name="never checked")
    fresh = Item(url="https://b.com", name="fresh", last_checked=now - timedelta(minutes=10))
    own = Item(
        url="https://c.com", name="own interval", check_interval_minutes=5, last_checked=now - timedelta(minutes=6)
    )
    via_profile = Item(
        url="https://d.com",
        name="profile",
        notification_profile_id=profile.id,
        last_checked=now - timedelta(minutes=30),
    )
    stale = Item(url="https://e.com", name="stale", last_checked=now - timedelta(hours=3))
    db.add_all([never, fresh, own, via_profile, stale])
    await db.commit()

    due = await checks.claim_due(db, AppSettings(refresh_interval_minutes=120))

    assert sorted(due) == sorted([never.id, own.id, stale.id])


def test_interval_never_drops_below_minimum():
    assert checks.interval_minutes(make_item(check_interval_minutes=1), 60) == checks.MIN_INTERVAL_MINUTES
    assert checks.interval_minutes(make_item(), 90) == 90


async def test_startup_releases_leftover_claims(db):
    item = Item(url="https://example.com", name="Stuck", is_refreshing=True, refresh_started_at=utcnow())
    db.add(item)
    await db.commit()

    await checks.release_all_claims()

    await db.refresh(item)
    assert item.is_refreshing is False


async def test_cancelled_check_releases_its_claim(db, monkeypatch):
    item = Item(url="https://example.com", name="Cancelled")
    db.add(item)
    await db.commit()
    await checks.claim(db, [item.id])
    monkeypatch.setattr(checks, "_slots", asyncio.Semaphore(0))  # queue forever

    task = asyncio.create_task(checks.check_item(item.id))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    await db.refresh(item)
    assert item.is_refreshing is False


# Full check


@pytest.fixture
async def claimed_item(db):
    profile = NotificationProfile(name="Alerts", apprise_url="json://localhost")
    db.add(profile)
    await db.flush()
    item = Item(
        url="https://example.com",
        name="Widget",
        current_price=120.0,
        target_price=100.0,
        notification_profile_id=profile.id,
    )
    db.add(item)
    await db.commit()
    await checks.claim(db, [item.id])
    return item


async def test_successful_check_saves_result_screenshot_and_notifies(db, claimed_item, png, monkeypatch):
    monkeypatch.setattr(checks.scraper, "capture", AsyncMock(return_value=Capture(png, "page text")))
    monkeypatch.setattr(checks.ai, "extract", AsyncMock(return_value=extraction(price=95.0)))
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(checks.notify, "send", send)

    await checks.check_item(claimed_item.id)

    await db.refresh(claimed_item)
    assert claimed_item.current_price == 95.0
    assert claimed_item.is_refreshing is False
    assert checks.screenshot_file(claimed_item.id).read_bytes() == png
    assert (await db.scalars(select(PriceHistory.price))).all() == [95.0]
    titles = [call.args[1] for call in send.await_args_list]
    assert titles == ["Price drop: Widget", "Target price reached: Widget"]


async def test_page_text_is_only_sent_when_enabled(db, claimed_item, png, monkeypatch):
    monkeypatch.setattr(checks.scraper, "capture", AsyncMock(return_value=Capture(png, "x" * 10_000)))
    extract = AsyncMock(return_value=extraction())
    monkeypatch.setattr(checks.ai, "extract", extract)
    monkeypatch.setattr(checks.notify, "send", AsyncMock())

    await checks.check_item(claimed_item.id)
    assert extract.await_args.kwargs["page_text"] is None

    await checks.app_settings.save(db, {"text_context_enabled": True, "text_context_length": 1000})
    await checks.check_item(claimed_item.id)
    assert extract.await_args.kwargs["page_text"] == "x" * 1000


async def test_scrape_failure_keeps_what_the_browser_saw(db, claimed_item, png, monkeypatch):
    error = ScrapeError("Page looks blocked by a bot check ('captcha')", Capture(png, "captcha"))
    monkeypatch.setattr(checks.scraper, "capture", AsyncMock(side_effect=error))

    await checks.check_item(claimed_item.id)

    await db.refresh(claimed_item)
    assert claimed_item.error_type == "scrape_failed"
    assert "bot check" in claimed_item.last_error
    assert claimed_item.consecutive_failures == 1
    assert claimed_item.is_refreshing is False
    assert checks.screenshot_file(claimed_item.id).exists()


async def test_ai_failure_reports_the_reason(db, claimed_item, png, monkeypatch):
    monkeypatch.setattr(checks.scraper, "capture", AsyncMock(return_value=Capture(png, "")))
    monkeypatch.setattr(checks.ai, "extract", AsyncMock(side_effect=ExtractionError("Invalid API key\ndetails")))

    await checks.check_item(claimed_item.id)

    await db.refresh(claimed_item)
    assert claimed_item.error_type == "ai_failed"
    assert claimed_item.last_error == "AI extraction failed: Invalid API key"


async def test_repeated_failures_pause_the_item(db, claimed_item, monkeypatch):
    monkeypatch.setattr(checks.scraper, "capture", AsyncMock(side_effect=ScrapeError("timeout")))
    await checks.app_settings.save(db, {"max_consecutive_failures": 2})

    await checks.check_item(claimed_item.id)
    await checks.check_item(claimed_item.id)

    await db.refresh(claimed_item)
    assert claimed_item.is_active is False
    assert claimed_item.error_type == "auto_deactivated"
    assert claimed_item.last_error.startswith("Paused after 2 failed checks")


async def test_scheduler_tick_claims_due_items(db, monkeypatch):
    item = Item(url="https://example.com", name="Due")
    db.add(item)
    await db.commit()
    enqueued = []
    monkeypatch.setattr(checks, "enqueue", lambda ids, jitter: enqueued.extend(ids))
    monkeypatch.setattr(checks, "HEARTBEAT_SECONDS", 0)

    task = asyncio.create_task(checks.run_scheduler())
    while not enqueued:
        await asyncio.sleep(0.01)
    task.cancel()

    assert enqueued == [item.id]
