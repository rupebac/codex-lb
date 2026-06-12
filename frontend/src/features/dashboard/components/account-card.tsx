import type { ReactNode } from "react";
import { Clock, ExternalLink, Play, RotateCcw, Zap } from "lucide-react";

import { usePrivacyStore } from "@/hooks/use-privacy";
import { cn } from "@/lib/utils";
import type { AccountSummary } from "@/features/dashboard/schemas";
import { formatCompactAccountId } from "@/utils/account-identifiers";
import {
  STATUS_DOT,
  normalizeStatus,
  quotaBarColor,
  quotaBarTrack,
} from "@/utils/account-status";
import { STATUS_LABELS } from "@/utils/constants";
import { formatDateTimeInline, formatPercentNullable, formatQuotaResetLabel, formatSlug } from "@/utils/formatters";

type AccountAction = "details" | "resume" | "reauth" | "warmup-toggle";

export type AccountCardProps = {
  account: AccountSummary;
  showAccountId?: boolean;
  onAction?: (account: AccountSummary, action: AccountAction) => void;
};

// Left-edge accent rendered via ::before so it never affects the card's box height.
const STATUS_ACCENT: Record<string, string> = {
  active: "before:bg-transparent",
  paused: "before:bg-amber-500",
  limited: "before:bg-orange-500",
  exceeded: "before:bg-red-500",
  deactivated: "before:bg-zinc-400",
};

// Text chip shown for non-active states so status never relies on dot colour alone
// (glanceable + WCAG 1.4.1). Active accounts stay dot-only to avoid header noise.
const STATUS_CHIP: Record<string, string> = {
  paused: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  limited: "bg-orange-500/15 text-orange-700 dark:text-orange-400",
  exceeded: "bg-red-500/15 text-red-700 dark:text-red-400",
  deactivated: "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400",
};

function percentTextColor(percent: number | null): string {
  if (percent === null) return "text-muted-foreground";
  if (percent >= 70) return "text-emerald-600 dark:text-emerald-400";
  if (percent >= 30) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function QuotaRow({
  label,
  percent,
  resetLabel,
}: {
  label: string;
  percent: number | null;
  resetLabel: string;
}) {
  const clamped = percent === null ? 0 : Math.max(0, Math.min(100, percent));
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <div className={cn("h-1.5 min-w-0 flex-1 overflow-hidden rounded-full", quotaBarTrack(clamped))}>
        <div
          className={cn("h-full rounded-full transition-all duration-500 ease-out", quotaBarColor(clamped))}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className={cn("w-9 shrink-0 text-right text-[11px] tabular-nums font-medium", percentTextColor(percent))}>
        {formatPercentNullable(percent)}
      </span>
      <span
        className="flex w-[4.25rem] shrink-0 items-center justify-end gap-1 text-[10px] text-muted-foreground"
        title={`Resets ${resetLabel}`}
      >
        <Clock className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
        <span className="truncate">{resetLabel}</span>
      </span>
    </div>
  );
}

export function AccountCard({ account, showAccountId = false, onAction }: AccountCardProps) {
  const blurred = usePrivacyStore((s) => s.blurred);
  const status = normalizeStatus(account.status);
  const statusLabel = STATUS_LABELS[status] ?? status;
  const primaryRemaining = account.usage?.primaryRemainingPercent ?? null;
  const secondaryRemaining = account.usage?.secondaryRemainingPercent ?? null;
  const weeklyOnly = account.windowMinutesPrimary == null && account.windowMinutesSecondary != null;

  const primaryReset = formatQuotaResetLabel(account.resetAtPrimary ?? null);
  const secondaryReset = formatQuotaResetLabel(account.resetAtSecondary ?? null);

  const title = account.displayName || account.email;
  const compactId = formatCompactAccountId(account.accountId);
  const planLabel = formatSlug(account.planType);
  const emailSubtitle =
    account.displayName && account.displayName !== account.email ? account.email : null;

  // Identity is always ONE line so an alias can never change the card's height.
  // Primary label = alias when set, otherwise the display name / email.
  const primaryLabel = account.alias || title;
  const secondaryEmail = account.alias ? account.email : emailSubtitle;

  const warmupEnabled = account.limitWarmupEnabled;
  const warmupToggleLabel = `${warmupEnabled ? "Disable" : "Enable"} limit warm-up for ${title}`;
  const warmupDetail = account.limitWarmup
    ? `${formatSlug(account.limitWarmup.status)} | ${account.limitWarmup.window === "primary" ? "5h" : "weekly"} | ${formatSlug(account.limitWarmup.model)} | ${formatDateTimeInline(account.limitWarmup.completedAt ?? account.limitWarmup.attemptedAt)}`
    : "No attempts";
  const warmupTitle = `Warm-up ${warmupEnabled ? "on" : "off"} — ${warmupDetail}`;

  return (
    <div
      className={cn(
        "card-hover relative flex h-[104px] flex-col overflow-hidden rounded-xl border bg-card p-3",
        "before:absolute before:left-0 before:top-0 before:h-full before:w-[3px]",
        STATUS_ACCENT[status] ?? STATUS_ACCENT.deactivated,
      )}
    >
      {/* Header — single fixed line: status dot, identity, plan, quick actions */}
      <div className="flex items-center gap-2">
        <span
          role="img"
          aria-label={statusLabel}
          title={statusLabel}
          className={cn("h-2 w-2 shrink-0 rounded-full", STATUS_DOT[status])}
        />
        <span className="min-w-0 flex-1 truncate text-sm leading-tight" title={`${title}${showAccountId ? ` · ID ${compactId}` : ""}`}>
          <span className={cn("font-semibold", blurred && "privacy-blur")}>{primaryLabel}</span>
          {secondaryEmail ? (
            <span className="font-normal text-muted-foreground">
              {" · "}
              <span className={blurred ? "privacy-blur" : undefined}>{secondaryEmail}</span>
            </span>
          ) : null}
          {showAccountId ? (
            <span className="font-normal text-muted-foreground">{` · ID ${compactId}`}</span>
          ) : null}
        </span>

        {status !== "active" ? (
          <span className={cn("shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium leading-none", STATUS_CHIP[status])}>
            {statusLabel}
          </span>
        ) : null}

        <span className="shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground">
          {planLabel}
        </span>

        <div className="flex shrink-0 items-center">
          {status === "paused" && (
            <IconButton
              label={`Resume ${title}`}
              onClick={() => onAction?.(account, "resume")}
              className="text-emerald-600 hover:bg-emerald-500/10 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
            >
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
            </IconButton>
          )}
          {status === "deactivated" && (
            <IconButton
              label={`Re-authenticate ${title}`}
              onClick={() => onAction?.(account, "reauth")}
              className="text-amber-600 hover:bg-amber-500/10 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-300"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            </IconButton>
          )}
          <IconButton
            label={warmupToggleLabel}
            title={warmupTitle}
            onClick={() => onAction?.(account, "warmup-toggle")}
            className={
              warmupEnabled
                ? "text-primary hover:bg-primary/10 hover:text-primary"
                : "text-muted-foreground hover:text-foreground"
            }
          >
            <Zap className="h-3.5 w-3.5" aria-hidden="true" />
          </IconButton>
          <IconButton
            label={`Open details for ${title}`}
            title="Open account details"
            onClick={() => onAction?.(account, "details")}
            className="text-muted-foreground hover:text-foreground"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </IconButton>
        </div>
      </div>

      {/* Quota — pinned to the bottom so weekly-only cards keep the same height */}
      <div className="mt-auto space-y-1.5 pt-2.5">
        {!weeklyOnly && <QuotaRow label="5h" percent={primaryRemaining} resetLabel={primaryReset} />}
        <QuotaRow label="Weekly" percent={secondaryRemaining} resetLabel={secondaryReset} />
      </div>
    </div>
  );
}

function IconButton({
  label,
  title,
  className,
  onClick,
  children,
}: {
  label: string;
  title?: string;
  className?: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={title ?? label}
      onClick={onClick}
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors",
        className,
      )}
    >
      {children}
    </button>
  );
}
