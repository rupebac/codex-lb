"""add per-account Codex installation IDs

Revision ID: 20260610_000000_add_accounts_codex_installation_id
Revises: 20260607_000000_merge_weekly_monthly_useragent_heads
Create Date: 2026-06-10
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260610_000000_add_accounts_codex_installation_id"
down_revision = "20260607_000000_merge_weekly_monthly_useragent_heads"
branch_labels = None
depends_on = None

_COLUMN_NAME = "codex_installation_id"


def _columns(connection: Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if not columns:
        return

    if _COLUMN_NAME not in columns:
        with op.batch_alter_table("accounts") as batch_op:
            batch_op.add_column(sa.Column(_COLUMN_NAME, sa.String(length=36), nullable=True))

    rows = bind.execute(
        sa.text(
            """
            SELECT id
            FROM accounts
            WHERE codex_installation_id IS NULL
               OR codex_installation_id = ''
            """
        )
    ).fetchall()
    for row in rows:
        bind.execute(
            sa.text(
                """
                UPDATE accounts
                SET codex_installation_id = :codex_installation_id
                WHERE id = :account_id
                """
            ),
            {
                "account_id": row[0],
                "codex_installation_id": str(uuid.uuid4()),
            },
        )

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.alter_column(
            _COLUMN_NAME,
            existing_type=sa.String(length=36),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if _COLUMN_NAME not in columns:
        return

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column(_COLUMN_NAME)
