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
        "duels",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("challenger_id", sa.BigInteger(), nullable=False),
        sa.Column("opponent_id", sa.BigInteger(), nullable=False),
        sa.Column("quest_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("challenger_score", sa.SmallInteger()),
        sa.Column("opponent_score", sa.SmallInteger()),
        sa.Column("winner_id", sa.BigInteger()),
        sa.Column("elo_delta", sa.SmallInteger()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_duels_challenger", "duels", ["challenger_id", "status"])
    op.create_index("ix_duels_opponent", "duels", ["opponent_id", "status"])

    op.create_table(
        "leaderboard_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("period", sa.String(8), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("xp_gained", sa.Integer(), server_default="0"),
        sa.Column("quests_done", sa.SmallInteger(), server_default="0"),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("period", "period_start", "user_id", name="uq_leaderboard_user_period"),
    )
    op.create_index("ix_leaderboard_period_rank", "leaderboard_entries", ["period", "period_start", "rank"])

    op.create_table(
        "follows",
        sa.Column("follower_id", sa.BigInteger(), primary_key=True),
        sa.Column("followed_id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_follows_followed", "follows", ["followed_id"])


def downgrade() -> None:
    op.drop_table("follows")
    op.drop_table("leaderboard_entries")
    op.drop_table("duels")
