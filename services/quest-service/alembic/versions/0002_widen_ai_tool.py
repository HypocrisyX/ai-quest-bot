"""widen quests.ai_tool to 64 chars

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "quests",
        "ai_tool",
        type_=sa.String(64),
        existing_type=sa.String(32),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "quests",
        "ai_tool",
        type_=sa.String(32),
        existing_type=sa.String(64),
        existing_nullable=True,
    )
