"""add account egress probe columns

Revision ID: 20260612_000000_add_account_egress_probe_columns
Revises: 20260607_000000_merge_routing_and_quota_planner_heads
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260612_000000_add_account_egress_probe_columns"
down_revision = "20260607_000000_merge_routing_and_quota_planner_heads"
branch_labels = None
depends_on = None


_NEW_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("egress_last_observed_ip", sa.Column("egress_last_observed_ip", sa.String(), nullable=True)),
    ("egress_last_observed_at", sa.Column("egress_last_observed_at", sa.DateTime(), nullable=True)),
    ("egress_last_checked_at", sa.Column("egress_last_checked_at", sa.DateTime(), nullable=True)),
    (
        "egress_last_probe_status",
        sa.Column(
            "egress_last_probe_status",
            sa.String(),
            nullable=False,
            server_default="unknown",
        ),
    ),
    ("egress_last_probe_error", sa.Column("egress_last_probe_error", sa.Text(), nullable=True)),
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
