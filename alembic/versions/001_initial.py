"""initial

Revision ID: 001
Revises:
Create Date: 2026-05-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_idempotency_key", "payments", ["idempotency_key"], unique=True)

    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_payment_id", "outbox", ["payment_id"])
    op.create_index("ix_outbox_pending", "outbox", ["processed_at"], postgresql_where=sa.text("processed_at IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_outbox_pending", table_name="outbox")
    op.drop_index("ix_outbox_payment_id", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_payments_idempotency_key", table_name="payments")
    op.drop_table("payments")
