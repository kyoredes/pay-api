"""rename outbox to payment_outbox

Revision ID: 004
Revises: 002
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("outbox", "payment_outbox")
    op.execute("ALTER INDEX ix_outbox_payment_id RENAME TO ix_payment_outbox_payment_id")
    op.execute("ALTER INDEX ix_outbox_pending RENAME TO ix_payment_outbox_pending")
    op.execute(
        "ALTER INDEX ix_outbox_pending_unclaimed RENAME TO ix_payment_outbox_pending_unclaimed"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_payment_outbox_pending_unclaimed RENAME TO ix_outbox_pending_unclaimed"
    )
    op.execute("ALTER INDEX ix_payment_outbox_pending RENAME TO ix_outbox_pending")
    op.execute("ALTER INDEX ix_payment_outbox_payment_id RENAME TO ix_outbox_payment_id")
    op.rename_table("payment_outbox", "outbox")
