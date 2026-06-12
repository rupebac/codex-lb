import type { AccountEgressStatus, AccountSummary } from "@/features/accounts/schemas";

export type EgressWarningCode = "local_dns_risk" | (string & {});

export function resolveEgressPrimaryStatus(
  egress: AccountEgressStatus | null | undefined,
): string {
  return egress?.status ?? "unknown";
}

export function egressPrimaryChipLabel(status: string | undefined): string {
  switch (status) {
    case "ok":
      return "Egress OK";
    case "direct_egress":
      return "Direct egress";
    case "shared_egress":
      return "Shared IP";
    case "probe_failed":
      return "Probe failed";
    case "unknown":
    default:
      return "Egress unknown";
  }
}

export function egressWarningChipLabel(warning: string): string {
  switch (warning) {
    case "local_dns_risk":
      return "Local DNS risk";
    default:
      return warning;
  }
}

export function egressWarningDescription(warning: string): string {
  switch (warning) {
    case "local_dns_risk":
      return "Local DNS resolution may leak destination hostnames before the SOCKS5 tunnel.";
    default:
      return warning;
  }
}

const primaryChipClassMap: Record<string, string> = {
  ok: "bg-emerald-500/15 text-emerald-700 border-emerald-500/20 dark:text-emerald-400",
  unknown: "bg-zinc-500/10 text-zinc-600 border-zinc-500/20 dark:text-zinc-400",
  direct_egress: "bg-amber-500/15 text-amber-700 border-amber-500/20 dark:text-amber-400",
  shared_egress: "bg-red-500/15 text-red-700 border-red-500/20 dark:text-red-400",
  probe_failed: "bg-red-500/15 text-red-700 border-red-500/20 dark:text-red-400",
};

export const egressWarningChipClassName =
  "bg-amber-500/15 text-amber-700 border-amber-500/20 dark:text-amber-400";

export function egressPrimaryChipClassName(status: string | undefined): string {
  return primaryChipClassMap[status ?? "unknown"] ?? primaryChipClassMap.unknown;
}

export function shouldShowObservedIp(
  egress: AccountEgressStatus | null | undefined,
): egress is AccountEgressStatus & { observedIp: string } {
  if (!egress?.observedIp) {
    return false;
  }
  return egress.status !== "probe_failed";
}

export function buildEgressPrimaryChipTitle(
  egress: AccountEgressStatus | null | undefined,
): string {
  const status = resolveEgressPrimaryStatus(egress);
  const parts = [egressPrimaryChipLabel(status)];
  if (shouldShowObservedIp(egress)) {
    parts.push(`Observed IP ${egress.observedIp}`);
  }
  if (egress?.checkedAt) {
    try {
      parts.push(`Checked ${new Date(egress.checkedAt).toLocaleString()}`);
    } catch {
      parts.push(`Checked ${egress.checkedAt}`);
    }
  }
  if (egress?.status === "probe_failed" && egress.error) {
    parts.push(egress.error);
  }
  return parts.join(" · ");
}

/** List rows omit the unknown chip for direct, never-probed accounts to save space. */
export function shouldShowAccountListEgressChips(account: AccountSummary): boolean {
  if (account.egress == null) {
    return true;
  }
  if (account.proxy) {
    return true;
  }
  if (account.egress.warnings?.length) {
    return true;
  }
  return account.egress.status !== "unknown";
}
