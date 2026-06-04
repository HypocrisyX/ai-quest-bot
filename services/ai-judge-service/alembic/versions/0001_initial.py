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
        "ai_evaluations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("quest_id", sa.Integer(), nullable=False),
        sa.Column("attempt_num", sa.SmallInteger(), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("ai_output", sa.Text()),
        sa.Column("score", sa.SmallInteger()),
        sa.Column("feedback", sa.Text()),
        sa.Column("criteria_scores", JSONB()),
        sa.Column("model_used", sa.String(32)),
        sa.Column("tokens_used", sa.Integer()),
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_eval_user_quest", "ai_evaluations", ["user_id", "quest_id"])
    op.create_index("ix_ai_eval_date", "ai_evaluations", ["evaluated_at"])


def downgrade() -> None:
    op.drop_table("ai_evaluations")
