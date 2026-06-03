"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_levels",
        sa.Column("level", sa.SmallInteger(), primary_key=True),
        sa.Column("title", sa.String(64), nullable=False),
        sa.Column("xp_required", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("requires_sub", sa.Boolean(), server_default="false"),
        sa.Column("reward_crystals", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "quests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("level_min", sa.SmallInteger(), sa.ForeignKey("game_levels.level"), nullable=False),
        sa.Column("level_max", sa.SmallInteger()),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("ai_tool", sa.String(32)),
        sa.Column("xp_reward", sa.Integer(), server_default="50"),
        sa.Column("crystal_reward", sa.Integer(), server_default="0"),
        sa.Column("time_limit_sec", sa.Integer()),
        sa.Column("order_index", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_quests_level_type", "quests", ["level_min", "type", "is_active"])

    op.create_table(
        "quest_criteria",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion", sa.String(128), nullable=False),
        sa.Column("weight", sa.SmallInteger(), server_default="1"),
        sa.Column("description", sa.Text()),
    )

    op.create_table(
        "quest_hints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.SmallInteger(), nullable=False),
        sa.Column("cost", sa.SmallInteger(), server_default="5"),
        sa.Column("text", sa.Text(), nullable=False),
    )

    op.create_table(
        "user_quest_progress",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("status", sa.String(16), server_default="in_progress"),
        sa.Column("attempts", sa.SmallInteger(), server_default="0"),
        sa.Column("best_score", sa.SmallInteger()),
        sa.Column("xp_earned", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("user_id", "quest_id", name="uq_user_quest"),
    )
    op.create_index("ix_user_quest_progress_user_status", "user_quest_progress", ["user_id", "status"])

    op.create_table(
        "user_hints_used",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("hint_id", sa.Integer(), sa.ForeignKey("quest_hints.id"), primary_key=True),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "daily_quests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("level_min", sa.SmallInteger(), nullable=False),
        sa.Column("xp_bonus", sa.Integer(), server_default="25"),
        sa.UniqueConstraint("date", "level_min", name="uq_daily_level"),
    )

    op.create_table(
        "user_daily_completions",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("daily_id", sa.Integer(), sa.ForeignKey("daily_quests.id"), primary_key=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_daily_completions")
    op.drop_table("daily_quests")
    op.drop_table("user_hints_used")
    op.drop_table("user_quest_progress")
    op.drop_table("quest_hints")
    op.drop_table("quest_criteria")
    op.drop_table("quests")
    op.drop_table("game_levels")
