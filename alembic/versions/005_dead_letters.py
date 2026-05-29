"""add dead_letters table

Revision ID: 005
Revises: 004
Create Date: 2026-05-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dead_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_dead_letters_payment_id", "dead_letters", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_dead_letters_payment_id", table_name="dead_letters")
    op.drop_table("dead_letters")
