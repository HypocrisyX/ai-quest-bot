"""add shop columns to user_stats

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_stats", sa.Column("streak_freeze_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_stats", sa.Column("free_hints", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_stats", sa.Column("quest_skips", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("user_stats", "quest_skips")
    op.drop_column("user_stats", "free_hints")
    op.drop_column("user_stats", "streak_freeze_count")
