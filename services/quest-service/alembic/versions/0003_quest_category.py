"""add quests.category (text/image/video)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_IMAGE_TITLES = (
    "Первая генерация изображения",
    "Стиль и атмосфера",
    "Negative prompts",
    "Параметры: соотношение сторон и детали",
    "Итерируй до результата",
)


def upgrade() -> None:
    op.add_column(
        "quests",
        sa.Column("category", sa.String(16), nullable=False, server_default="text"),
    )
    # Backfill: tag the image-generation quests; everything else stays 'text'.
    op.execute(
        sa.text("UPDATE quests SET category = 'image' WHERE title = ANY(:titles)").bindparams(
            sa.bindparam("titles", value=list(_IMAGE_TITLES))
        )
    )


def downgrade() -> None:
    op.drop_column("quests", "category")
