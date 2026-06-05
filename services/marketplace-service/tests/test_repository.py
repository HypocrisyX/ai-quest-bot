"""Tests for marketplace-service repository."""
import pytest
from app import repository as repo
from app.schemas import ListingCreate
from pydantic import ValidationError


async def _make_listing(db, seller_id=1, price=100):
    return await repo.create_listing(
        db, seller_id=seller_id, title="Prompt", description="desc",
        price=price, payload_text="secret", payload_file_id=None, payload_url=None,
    )


async def test_create_and_get_listing(db):
    listing = await _make_listing(db)
    found = await repo.get_listing(db, listing.id)
    assert found is not None
    assert found.title == "Prompt"
    assert found.status == "active"


async def test_list_active_excludes_seller(db):
    await _make_listing(db, seller_id=10)
    data = await repo.list_active(db, exclude_seller=10)
    assert data["total"] == 0  # own listing excluded
    data2 = await repo.list_active(db, exclude_seller=99)
    assert data2["total"] == 1


async def test_record_purchase_bumps_sales(db):
    listing = await _make_listing(db, seller_id=1)
    purchase = await repo.record_purchase(db, listing.id, buyer_id=2, price=100, seller_earned=90)
    assert purchase is not None
    refreshed = await repo.get_listing(db, listing.id)
    assert refreshed.sales_count == 1


async def test_record_purchase_idempotent(db):
    listing = await _make_listing(db)
    await repo.record_purchase(db, listing.id, buyer_id=2, price=100, seller_earned=90)
    again = await repo.record_purchase(db, listing.id, buyer_id=2, price=100, seller_earned=90)
    assert again is None  # already bought
    refreshed = await repo.get_listing(db, listing.id)
    assert refreshed.sales_count == 1  # not double-counted


async def test_has_purchased(db):
    listing = await _make_listing(db)
    assert await repo.has_purchased(db, listing.id, 2) is False
    await repo.record_purchase(db, listing.id, buyer_id=2, price=100, seller_earned=90)
    assert await repo.has_purchased(db, listing.id, 2) is True


async def test_seller_stats(db):
    listing = await _make_listing(db, seller_id=5, price=100)
    await repo.record_purchase(db, listing.id, buyer_id=2, price=100, seller_earned=90)
    await repo.record_purchase(db, listing.id, buyer_id=3, price=100, seller_earned=90)
    stats = await repo.seller_stats(db, 5)
    assert stats["listings"] == 1
    assert stats["sales"] == 2
    assert stats["earned"] == 180


async def test_remove_listing(db):
    listing = await _make_listing(db)
    assert await repo.remove_listing(db, listing.id) is True
    data = await repo.list_active(db)
    assert data["total"] == 0


# ── validation (Pydantic Field constraints) ───────────────────────────────────

def test_listing_price_below_min_rejected():
    with pytest.raises(ValidationError):
        ListingCreate(seller_id=1, title="X", price=5, payload_text="y")


def test_listing_price_above_max_rejected():
    with pytest.raises(ValidationError):
        ListingCreate(seller_id=1, title="X", price=99999, payload_text="y")


def test_listing_empty_title_rejected():
    with pytest.raises(ValidationError):
        ListingCreate(seller_id=1, title="", price=100, payload_text="y")


def test_listing_empty_payload_rejected():
    with pytest.raises(ValidationError):
        ListingCreate(seller_id=1, title="X", price=100, payload_text="")


def test_listing_valid_accepted():
    listing = ListingCreate(seller_id=1, title="OK", price=100, payload_text="good")
    assert listing.price == 100
