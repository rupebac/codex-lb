"""Merge routing strategies, quota planner, and all parallel heads.

Revision ID: 20260607_000000_merge_routing_and_quota_planner_heads
Revises: all parallel branch heads into one.
Create Date: 2026-06-07
"""

from __future__ import annotations

revision = "20260607_000000_merge_routing_and_quota_planner_heads"
down_revision = (
    "20260427_130000_add_warmup_model_and_request_kind",
    "20260509_010000_add_additional_quota_routing_policies",
    "20260515_000000_add_prefer_earlier_reset_window",
    "20260515_020000_add_split_sticky_budget_thresholds",
    "20260520_030000_add_quota_planner",
    "20260531_000000_add_accounts_codex_installation_id",
    "20260531_000000_add_single_account_routing",
    "20260603_000000_add_weekly_pace_working_days",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
