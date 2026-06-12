import { useState } from "react";
import { AlertTriangle, Globe, KeyRound, Network, Radar, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { AccountProxyDialog } from "@/features/accounts/components/account-proxy-dialog";
import { useClearAccountProxy, useProbeAccountEgress } from "@/features/accounts/hooks/use-accounts";
import type { AccountSummary } from "@/features/accounts/schemas";

export type AccountProxySectionProps = {
  account: AccountSummary;
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function egressStatusLabel(status: string | undefined): string {
  switch (status) {
    case "ok":
      return "Verified";
    case "direct_egress":
      return "Direct egress";
    case "shared_egress":
      return "Shared IP";
    case "probe_failed":
      return "Probe failed";
    case "unknown":
    default:
      return "Not verified";
  }
}

function egressStatusVariant(status: string | undefined): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "ok":
      return "default";
    case "direct_egress":
    case "shared_egress":
      return "secondary";
    case "probe_failed":
      return "destructive";
    default:
      return "outline";
  }
}

export function AccountProxySection({ account }: AccountProxySectionProps) {
  const [editorOpen, setEditorOpen] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const clearProxy = useClearAccountProxy();
  const probeEgress = useProbeAccountEgress();

  const proxy = account.proxy ?? null;
  const egress = account.egress ?? null;

  return (
    <section
      aria-label="Network egress"
      className="space-y-2 border-t pt-4"
      data-testid="account-proxy-section"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Network className="h-3.5 w-3.5" /> Network egress
        </h3>
        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 gap-1.5 text-xs"
            onClick={() => probeEgress.mutate(account.accountId)}
            disabled={probeEgress.isPending || clearProxy.isPending}
            data-testid="egress-probe-button"
          >
            <Radar className="h-3.5 w-3.5" />
            {probeEgress.isPending ? "Probing…" : "Verify egress"}
          </Button>
          {proxy ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 gap-1.5 text-xs"
                onClick={() => setEditorOpen(true)}
                disabled={clearProxy.isPending || probeEgress.isPending}
              >
                Edit proxy
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 gap-1.5 text-xs text-destructive hover:text-destructive"
                onClick={() => setConfirmRemove(true)}
                disabled={clearProxy.isPending || probeEgress.isPending}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remove
              </Button>
            </>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 gap-1.5 text-xs"
              onClick={() => setEditorOpen(true)}
              disabled={probeEgress.isPending}
            >
              Configure proxy
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={egressStatusVariant(egress?.status)} data-testid="egress-status-badge">
          {egressStatusLabel(egress?.status)}
        </Badge>
        {egress?.observedIp ? (
          <span className="font-mono text-muted-foreground" data-testid="egress-observed-ip">
            {egress.observedIp}
          </span>
        ) : null}
        {egress?.checkedAt ? (
          <span className="text-muted-foreground">Checked {formatTimestamp(egress.checkedAt)}</span>
        ) : null}
      </div>

      {egress?.warnings?.length ? (
        <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-400" data-testid="egress-warnings">
          {egress.warnings.map((warning) => (
            <li key={warning} className="flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              {warning === "local_dns_risk"
                ? "Local DNS resolution may leak destination hostnames before the SOCKS5 tunnel."
                : warning}
            </li>
          ))}
        </ul>
      ) : null}

      {egress?.error ? (
        <p className="text-xs text-destructive" data-testid="egress-error">
          {egress.error}
        </p>
      ) : null}

      {proxy ? (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Endpoint</dt>
          <dd className="font-mono">
            socks5{proxy.remoteDns ? "h" : ""}://
            {proxy.username ? `${proxy.username}@` : ""}
            {proxy.host}:{proxy.port}
          </dd>
          <dt className="text-muted-foreground">DNS</dt>
          <dd>
            <span className="inline-flex items-center gap-1">
              <Globe className="h-3 w-3" />
              {proxy.remoteDns ? "Resolved at proxy (recommended)" : "Resolved locally"}
            </span>
          </dd>
          <dt className="text-muted-foreground">Auth</dt>
          <dd>
            <span className="inline-flex items-center gap-1">
              <KeyRound className="h-3 w-3" />
              {proxy.hasPassword ? "Password configured" : "No password"}
            </span>
          </dd>
          {proxy.label ? (
            <>
              <dt className="text-muted-foreground">Label</dt>
              <dd>{proxy.label}</dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">Last validated</dt>
          <dd>{formatTimestamp(proxy.lastValidatedAt)}</dd>
        </dl>
      ) : (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Endpoint</dt>
          <dd>Direct egress</dd>
        </dl>
      )}

      <AccountProxyDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        accountId={account.accountId}
        existing={proxy}
      />

      <ConfirmDialog
        open={confirmRemove}
        title="Remove egress proxy?"
        description="The account will go back to direct egress on the next request."
        onOpenChange={setConfirmRemove}
        onConfirm={async () => {
          try {
            await clearProxy.mutateAsync(account.accountId);
          } finally {
            setConfirmRemove(false);
          }
        }}
        confirmLabel={clearProxy.isPending ? "Removing…" : "Remove proxy"}
      />
    </section>
  );
}
