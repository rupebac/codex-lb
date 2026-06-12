"""add account token refresh schedule columns

Revision ID: 20260612_000001_add_account_token_refresh_schedule_columns
Revises: 20260612_000000_add_account_egress_probe_columns
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260612_000001_add_account_token_refresh_schedule_columns"
down_revision = "20260612_000000_add_account_egress_probe_columns"
branch_labels = None
depends_on = None


_NEW_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("token_refresh_next_allowed_at", sa.Column("token_refresh_next_allowed_at", sa.DateTime(), nullable=True)),
    ("token_refresh_last_attempt_at", sa.Column("token_refresh_last_attempt_at", sa.DateTime(), nullable=True)),
    ("token_refresh_last_result", sa.Column("token_refresh_last_result", sa.String(), nullable=True)),
    ("token_refresh_last_reason", sa.Column("token_refresh_last_reason", sa.String(), nullable=True)),
    (
        "token_refresh_failure_count",
        sa.Column(
            "token_refresh_failure_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    ),
)


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

    missing = [(name, column) for name, column in _NEW_COLUMNS if name not in columns]
    if not missing:
        return

    with op.batch_alter_table("accounts") as batch_op:
        for _, column in missing:
            batch_op.add_column(column)


def downgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if not columns:
        return

    present = [name for name, _ in _NEW_COLUMNS if name in columns]
    if not present:
        return

    with op.batch_alter_table("accounts") as batch_op:
        for name in reversed(present):
            batch_op.drop_column(name)
