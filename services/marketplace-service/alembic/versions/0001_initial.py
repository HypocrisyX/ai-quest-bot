"""initial marketplace schema

Revision ID: 0001
Revises:
Create Date: 2026-06-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("seller_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("payload_text", sa.Text(), nullable=False),
        sa.Column("payload_file_id", sa.String(256)),
        sa.Column("payload_url", sa.String(512)),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_listings_status", "listings", ["status", "created_at"])
    op.create_index("ix_listings_seller", "listings", ["seller_id"])

    op.create_table(
        "purchases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("listing_id", sa.BigInteger(), sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("seller_earned", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("listing_id", "buyer_id", name="uq_purchase_listing_buyer"),
    )
    op.create_index("ix_purchases_buyer", "purchases", ["buyer_id"])


def downgrade() -> None:
    op.drop_table("purchases")
    op.drop_table("listings")
