from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Listing, Purchase

MAX_LISTINGS_PER_SELLER = 10


async def count_seller_active(session: AsyncSession, seller_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.seller_id == seller_id, Listing.status == "active"
        )
    ) or 0


async def create_listing(
    session: AsyncSession,
    seller_id: int,
    title: str,
    description: Optional[str],
    price: int,
    payload_text: str,
    payload_file_id: Optional[str],
    payload_url: Optional[str],
) -> Listing:
    listing = Listing(
        seller_id=seller_id,
        title=title,
        description=description,
        price=price,
        payload_text=payload_text,
        payload_file_id=payload_file_id,
        payload_url=payload_url,
    )
    session.add(listing)
    await session.flush()
    return listing


async def get_listing(session: AsyncSession, listing_id: int) -> Optional[Listing]:
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    return result.scalar_one_or_none()


async def list_active(
    session: AsyncSession, limit: int = 10, offset: int = 0,
    exclude_seller: Optional[int] = None,
) -> dict:
    base = select(Listing).where(Listing.status == "active")
    if exclude_seller is not None:
        base = base.where(Listing.seller_id != exclude_seller)

    total = await session.scalar(
        select(func.count()).select_from(base.subquery())
    )
    result = await session.execute(
        base.order_by(Listing.created_at.desc()).limit(limit).offset(offset)
    )
    return {"total": total or 0, "listings": list(result.scalars())}


async def get_seller_listings(session: AsyncSession, seller_id: int) -> list[Listing]:
    result = await session.execute(
        select(Listing)
        .where(Listing.seller_id == seller_id, Listing.status == "active")
        .order_by(Listing.created_at.desc())
    )
    return list(result.scalars())


async def remove_listing(session: AsyncSession, listing_id: int) -> bool:
    listing = await get_listing(session, listing_id)
    if listing is None:
        return False
    listing.status = "removed"
    await session.flush()
    return True


async def has_purchased(
    session: AsyncSession, listing_id: int, buyer_id: int
) -> bool:
    result = await session.execute(
        select(Purchase).where(
            Purchase.listing_id == listing_id,
            Purchase.buyer_id == buyer_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def record_purchase(
    session: AsyncSession, listing_id: int, buyer_id: int,
    price: int, seller_earned: int,
) -> Optional[Purchase]:
    """Record a purchase + bump sales_count. Returns None if already bought."""
    if await has_purchased(session, listing_id, buyer_id):
        return None
    purchase = Purchase(
        listing_id=listing_id, buyer_id=buyer_id,
        price=price, seller_earned=seller_earned,
    )
    session.add(purchase)
    listing = await get_listing(session, listing_id)
    if listing:
        listing.sales_count = (listing.sales_count or 0) + 1
    await session.flush()
    return purchase


async def get_buyer_purchases(session: AsyncSession, buyer_id: int) -> list[dict]:
    """Purchases joined with listing payload, newest first."""
    result = await session.execute(
        select(Listing, Purchase.created_at)
        .join(Purchase, Purchase.listing_id == Listing.id)
        .where(Purchase.buyer_id == buyer_id)
        .order_by(Purchase.created_at.desc())
    )
    return [{"listing": listing, "purchased_at": purchased_at} for listing, purchased_at in result]


async def seller_stats(session: AsyncSession, seller_id: int) -> dict:
    listings = await session.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.seller_id == seller_id, Listing.status == "active"
        )
    )
    sales_earned = await session.execute(
        select(func.count(Purchase.id), func.coalesce(func.sum(Purchase.seller_earned), 0))
        .join(Listing, Listing.id == Purchase.listing_id)
        .where(Listing.seller_id == seller_id)
    )
    sales, earned = sales_earned.one()
    return {"listings": listings or 0, "sales": sales or 0, "earned": earned or 0}


async def admin_list_listings(session: AsyncSession, limit: int = 20) -> list[Listing]:
    result = await session.execute(
        select(Listing).order_by(Listing.created_at.desc()).limit(limit)
    )
    return list(result.scalars())
