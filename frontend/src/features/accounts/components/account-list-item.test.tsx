import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountListItem } from "@/features/accounts/components/account-list-item";
import { useAccountQuotaDisplayStore } from "@/hooks/use-account-quota-display";
import { createAccountSummary } from "@/test/mocks/factories";

describe("AccountListItem", () => {
  beforeEach(() => {
    useAccountQuotaDisplayStore.setState({ quotaDisplay: "both" });
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T12:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders neutral quota track when secondary remaining percent is unknown", () => {
    const account = createAccountSummary({
      usage: {
        primaryRemainingPercent: 82,
        secondaryRemainingPercent: null,
      },
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByTestId("mini-quota-track-weekly")).toHaveClass("bg-muted");
    expect(screen.queryByTestId("mini-quota-track-weekly-fill")).not.toBeInTheDocument();
    expect(screen.getByText("5h")).toBeInTheDocument();
    expect(screen.getByText("Weekly")).toBeInTheDocument();
    expect(screen.getByText("Reset in 1h")).toBeInTheDocument();
    expect(screen.getByText("Reset in 1d")).toBeInTheDocument();
  });

  it("omits the 5h row for weekly-only accounts", () => {
    const account = createAccountSummary({
      usage: {
        primaryRemainingPercent: null,
        secondaryRemainingPercent: 73,
      },
      resetAtPrimary: null,
      resetAtSecondary: "2026-01-02T12:00:00.000Z",
      windowMinutesPrimary: null,
      windowMinutesSecondary: 10_080,
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.queryByText("5h")).not.toBeInTheDocument();
    expect(screen.getByText("Weekly")).toBeInTheDocument();
    expect(screen.getByText("Reset in 1d")).toBeInTheDocument();
  });

  it("renders legacy primary quota data without window metadata", () => {
    const account = createAccountSummary({
      usage: {
        primaryRemainingPercent: 64,
        secondaryRemainingPercent: null,
      },
      resetAtPrimary: "2026-01-01T13:00:00.000Z",
      resetAtSecondary: null,
      windowMinutesPrimary: null,
      windowMinutesSecondary: null,
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByText("5h")).toBeInTheDocument();
    expect(screen.getByTestId("mini-quota-track-5h-fill")).toHaveStyle({ width: "64%" });
    expect(screen.getByText("Reset in 1h")).toBeInTheDocument();
    expect(screen.queryByText("Weekly")).not.toBeInTheDocument();
  });

  it("does not duplicate unavailable reset labels", () => {
    const account = createAccountSummary({
      usage: {
        primaryRemainingPercent: 64,
        secondaryRemainingPercent: null,
      },
      resetAtPrimary: null,
      resetAtSecondary: null,
      windowMinutesPrimary: 300,
      windowMinutesSecondary: null,
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByText("Reset --")).toBeInTheDocument();
    expect(screen.queryByText("Reset Reset unavailable")).not.toBeInTheDocument();
  });

  it("shows only the 5h row when the account quota preference is 5h", () => {
    useAccountQuotaDisplayStore.setState({ quotaDisplay: "5h" });

    const account = createAccountSummary({
      usage: {
        primaryRemainingPercent: 82,
        secondaryRemainingPercent: 73,
      },
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByText("5h")).toBeInTheDocument();
    expect(screen.queryByText("Weekly")).not.toBeInTheDocument();
  });

  it("renders quota fill when secondary remaining percent is available", () => {
    const account = createAccountSummary({
      usage: {
        primaryRemainingPercent: 82,
        secondaryRemainingPercent: 73,
      },
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByTestId("mini-quota-track-weekly-fill")).toHaveStyle({ width: "73%" });
  });

  it("renders compact egress chips without an extra list row", () => {
    const account = createAccountSummary({
      egress: {
        accountId: "acc_primary",
        status: "shared_egress",
        observedIp: "203.0.113.10",
        configuredProxy: true,
        proxyRemoteDns: true,
        sharedWithAccountIds: ["acc_other"],
        warnings: ["local_dns_risk"],
      },
    });

    const { container } = render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByTestId("account-list-egress-chip")).toHaveTextContent("Shared IP");
    expect(screen.getByTestId("egress-warning-chip-local_dns_risk")).toHaveTextContent("Local DNS risk");
    expect(screen.getByTestId("egress-status-chips")).toHaveClass("flex-wrap");
    expect(container.querySelectorAll("button")).toHaveLength(1);
  });

  it("falls back to egress unknown when summary egress is missing", () => {
    const account = createAccountSummary({ egress: undefined });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByTestId("account-list-egress-chip")).toHaveTextContent("Egress unknown");
  });

  it("omits egress chips for direct accounts with unknown status", () => {
    const account = createAccountSummary({
      egress: {
        accountId: "acc_primary",
        status: "unknown",
        configuredProxy: false,
        sharedWithAccountIds: [],
        warnings: [],
      },
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.queryByTestId("account-list-egress-chip")).not.toBeInTheDocument();
    expect(screen.getByText("Warm-up off")).toBeInTheDocument();
  });

  it("does not show observed IP text in the account list chips", () => {
    const account = createAccountSummary({
      egress: {
        accountId: "acc_primary",
        status: "probe_failed",
        observedIp: "93.184.216.34",
        error: "timeout",
        configuredProxy: false,
        proxyRemoteDns: true,
        sharedWithAccountIds: [],
        warnings: [],
      },
    });

    render(<AccountListItem account={account} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByTestId("account-list-egress-chip")).toHaveTextContent("Probe failed");
    expect(screen.queryByText("93.184.216.34")).not.toBeInTheDocument();
  });
});
