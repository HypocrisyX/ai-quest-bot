"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("template_code", sa.String(64), nullable=False),
        sa.Column("payload", JSONB()),
        sa.Column("channel", sa.String(16), server_default="telegram"),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_notifications_user_status", "notifications", ["user_id", "status"])
    op.create_index("ix_notifications_created", "notifications", ["created_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("category", sa.String(32), primary_key=True),
        sa.Column("channel", sa.String(16), primary_key=True),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_table("notification_templates")
