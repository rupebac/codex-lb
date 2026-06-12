"""Merge routing strategies, quota planner, and all parallel heads.

Revision ID: 20260607_000000_merge_routing_and_quota_planner_heads
Revises: all parallel branch heads into one.
Create Date: 2026-06-07
"""

from __future__ import annotations

revision = "20260607_000000_merge_routing_and_quota_planner_heads"
down_revision = (
    "20260310_000000_add_request_logs_transport",
    "20260312_000000_add_additional_usage_quota_key",
    "20260312_000000_split_sticky_sessions_primary_key_by_kind",
    "20260312_010000_merge_additional_usage_and_sticky_session_heads",
    "20260312_020000_merge_request_logs_transport_and_feature_heads",
    "20260312_020000_merge_request_logs_transport_and_sticky_heads",
    "20260312_120000_add_dashboard_upstream_stream_transport",
    "20260319_100937_increase_prompt_cache_ttl_to_1800s",
    "20260320_000000_add_request_log_requested_actual_tiers",
    "20260321_190000_tighten_dashboard_db_indexes",
    "20260328_140000_add_scheduler_leader_table",
    "20260406_010000_add_api_key_assignment_scope_flag",
    "20260407_000000_add_bridge_gateway_safe_mode",
    "20260408_000000_switch_import_without_overwrite_default_to_true",
    "20260409_000000_add_http_bridge_sessions",
    "20260410_000000_backfill_pristine_dashboard_settings_defaults",
    "20260410_030000_restore_import_without_overwrite_default_true",
    "20260415_160000_add_request_logs_response_lookup_index",
    "20260421_000000_add_dashboard_session_ttl_setting",
    "20260423_120000_add_api_key_limit_reset_at_index",
    "20260426_000000_add_dashboard_relative_availability_settings",
    "20260427_130000_add_warmup_model_and_request_kind",
    "20260509_010000_add_additional_quota_routing_policies",
    "20260513_000000_add_api_key_apply_to_codex_model",
    "20260515_000000_add_prefer_earlier_reset_window",
    "20260515_000000_soft_delete_request_logs_on_account_delete",
    "20260515_020000_add_split_sticky_budget_thresholds",
    "20260516_000000_add_sqlite_hot_path_indexes",
    "20260517_000000_merge_sqlite_hot_path_and_request_log_delete_heads",
    "20260518_010000_merge_http_bridge_and_sqlite_recovery_heads",
    "20260520_030000_add_quota_planner",
    "20260521_000000_add_account_security_work_authorized",
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
