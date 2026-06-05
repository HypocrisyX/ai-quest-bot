from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

PRICE_MIN = 10
PRICE_MAX = 10000


class ListingCreate(BaseModel):
    seller_id: int
    title: str = Field(min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=2000)
    price: int = Field(ge=PRICE_MIN, le=PRICE_MAX)
    payload_text: str = Field(min_length=1, max_length=8000)
    payload_file_id: Optional[str] = Field(default=None, max_length=256)
    payload_url: Optional[str] = Field(default=None, max_length=512)


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
    price: int = Field(ge=0)
    seller_earned: int = Field(ge=0)


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
