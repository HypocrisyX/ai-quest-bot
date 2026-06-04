"""duel invite codes, nullable opponent, stored answers

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
    # Existing rows (none expected) get a placeholder code; new schema requires it.
    op.add_column("duels", sa.Column("code", sa.String(16), nullable=True))
    op.add_column("duels", sa.Column("challenger_answer", sa.Text()))
    op.add_column("duels", sa.Column("opponent_answer", sa.Text()))
    op.execute("UPDATE duels SET code = 'legacy_' || id WHERE code IS NULL")
    op.alter_column("duels", "code", nullable=False)
    op.create_unique_constraint("uq_duels_code", "duels", ["code"])
    op.alter_column("duels", "opponent_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.alter_column("duels", "opponent_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_constraint("uq_duels_code", "duels", type_="unique")
    op.drop_column("duels", "opponent_answer")
    op.drop_column("duels", "challenger_answer")
    op.drop_column("duels", "code")
