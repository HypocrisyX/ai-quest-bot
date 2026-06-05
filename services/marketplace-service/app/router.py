from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository as repo
from .database import get_db
from .schemas import (
    ListingCreate,
    ListingOut,
    ListingPayloadOut,
    PurchaseOut,
    PurchaseRequest,
    SellerStatsOut,
)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/listings", response_model=ListingOut, status_code=201)
async def create_listing(data: ListingCreate, db: DB):
    return await repo.create_listing(
        db, data.seller_id, data.title, data.description, data.price,
        data.payload_text, data.payload_file_id, data.payload_url,
    )


@router.get("/listings")
async def list_listings(
    db: DB,
    limit: int = Query(10, le=50),
    offset: int = 0,
    exclude_seller: int | None = None,
):
    data = await repo.list_active(db, limit, offset, exclude_seller)
    return {
        "total": data["total"],
        "listings": [ListingOut.model_validate(x) for x in data["listings"]],
    }


@router.get("/listings/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, db: DB):
    listing = await repo.get_listing(db, listing_id)
    if not listing or listing.status != "active":
        raise HTTPException(404, "Listing not found")
    return listing


@router.get("/listings/{listing_id}/payload", response_model=ListingPayloadOut)
async def get_listing_payload(listing_id: int, db: DB):
    """Full listing including the deliverable payload (call after purchase)."""
    listing = await repo.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing


@router.delete("/listings/{listing_id}")
async def remove_listing(listing_id: int, db: DB):
    ok = await repo.remove_listing(db, listing_id)
    if not ok:
        raise HTTPException(404, "Listing not found")
    return {"removed": True}


@router.get("/sellers/{seller_id}/listings", response_model=list[ListingOut])
async def seller_listings(seller_id: int, db: DB):
    return await repo.get_seller_listings(db, seller_id)


@router.get("/sellers/{seller_id}/stats", response_model=SellerStatsOut)
async def seller_stats(seller_id: int, db: DB):
    return await repo.seller_stats(db, seller_id)


@router.get("/buyers/{buyer_id}/purchased/{listing_id}")
async def has_purchased(buyer_id: int, listing_id: int, db: DB):
    return {"purchased": await repo.has_purchased(db, listing_id, buyer_id)}


@router.post("/purchases", response_model=PurchaseOut | None, status_code=201)
async def record_purchase(data: PurchaseRequest, db: DB):
    purchase = await repo.record_purchase(
        db, data.listing_id, data.buyer_id, data.price, data.seller_earned
    )
    return purchase


@router.get("/buyers/{buyer_id}/purchases")
async def buyer_purchases(buyer_id: int, db: DB):
    items = await repo.get_buyer_purchases(db, buyer_id)
    return [
        {
            "listing": ListingOut.model_validate(it["listing"]),
            "purchased_at": it["purchased_at"],
        }
        for it in items
    ]


@router.get("/admin/listings", response_model=list[ListingOut])
async def admin_listings(db: DB, limit: int = Query(20, le=100)):
    return await repo.admin_list_listings(db, limit)
