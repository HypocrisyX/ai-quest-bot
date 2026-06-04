"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("language_code", sa.String(8), server_default="ru"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_stats",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("level", sa.SmallInteger(), server_default="1"),
        sa.Column("xp", sa.Integer(), server_default="0"),
        sa.Column("xp_to_next", sa.Integer(), server_default="100"),
        sa.Column("crystals", sa.Integer(), server_default="0"),
        sa.Column("elo_rating", sa.Integer(), server_default="1000"),
        sa.Column("streak_days", sa.SmallInteger(), server_default="0"),
        sa.Column("streak_last_at", sa.Date()),
        sa.Column("total_quests", sa.Integer(), server_default="0"),
        sa.Column("class_title", sa.String(32), server_default="Новичок"),
    )

    op.create_table(
        "subscriptions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("payment_ref", sa.String(128)),
    )
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("icon", sa.String(16)),
        sa.Column("xp_reward", sa.Integer(), server_default="0"),
        sa.Column("crystal_reward", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "user_achievements",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "achievement_id", sa.Integer(), sa.ForeignKey("achievements.id"), primary_key=True
        ),
        sa.Column("earned_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "crystal_transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(64)),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_crystal_transactions_user_date", "crystal_transactions", ["user_id", "created_at"]
    )

    op.create_table(
        "xp_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delta_xp", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(64)),
        sa.Column("level_after", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_xp_history_user_date", "xp_history", ["user_id", "created_at"])

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("referee_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("reward_granted", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_referrals_referrer", "referrals", ["referrer_id"])


def downgrade() -> None:
    op.drop_table("referrals")
    op.drop_table("xp_history")
    op.drop_table("crystal_transactions")
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_table("subscriptions")
    op.drop_table("user_stats")
    op.drop_table("users")
