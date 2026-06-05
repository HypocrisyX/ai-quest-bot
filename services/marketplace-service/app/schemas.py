from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ListingCreate(BaseModel):
    seller_id: int
    title: str
    description: Optional[str] = None
    price: int
    payload_text: str
    payload_file_id: Optional[str] = None
    payload_url: Optional[str] = None


class ListingOut(BaseModel):
    id: int
    seller_id: int
    title: str
    description: Optional[str]
    price: int
    status: str
    sales_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingPayloadOut(ListingOut):
    payload_text: str
    payload_file_id: Optional[str]
    payload_url: Optional[str]


class PurchaseRequest(BaseModel):
    listing_id: int
    buyer_id: int
    price: int
    seller_earned: int


class PurchaseOut(BaseModel):
    id: int
    listing_id: int
    buyer_id: int
    price: int
    seller_earned: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SellerStatsOut(BaseModel):
    listings: int
    sales: int
    earned: int
