"""add outbox claimed_at

Revision ID: 002
Revises: 001
Create Date: 2026-05-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("outbox", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_outbox_pending_unclaimed",
        "outbox",
        ["created_at"],
        postgresql_where=sa.text("processed_at IS NULL AND claimed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_pending_unclaimed", table_name="outbox")
    op.drop_column("outbox", "claimed_at")
