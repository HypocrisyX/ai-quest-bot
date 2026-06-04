"""add user_stats.xp_boost_quests

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_stats",
        sa.Column("xp_boost_quests", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_stats", "xp_boost_quests")
