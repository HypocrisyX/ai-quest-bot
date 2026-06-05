from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from .database import Base


class Listing(Base):
    __tablename__ = "listings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    seller_id = Column(BigInteger, nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text)
    price = Column(Integer, nullable=False)  # crystals (stars later)
    payload_text = Column(Text, nullable=False)      # the delivered content
    payload_file_id = Column(String(256))            # optional Telegram file_id
    payload_url = Column(String(512))                # optional link
    status = Column(String(16), nullable=False, server_default="active")  # active / removed
    sales_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    listing_id = Column(BigInteger, ForeignKey("listings.id"), nullable=False)
    buyer_id = Column(BigInteger, nullable=False)
    price = Column(Integer, nullable=False)          # price paid (snapshot)
    seller_earned = Column(Integer, nullable=False)  # after commission
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_id", name="uq_purchase_listing_buyer"),
    )
