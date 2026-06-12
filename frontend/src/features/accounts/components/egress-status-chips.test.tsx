import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  buildEgressPrimaryChipTitle,
  egressPrimaryChipLabel,
  shouldShowAccountListEgressChips,
  shouldShowObservedIp,
} from "@/features/accounts/components/egress-status-chip-utils";
import { EgressStatusChips } from "@/features/accounts/components/egress-status-chips";
import { createAccountSummary } from "@/test/mocks/factories";
import type { AccountEgressStatus } from "@/features/accounts/schemas";

const baseEgress: AccountEgressStatus = {
  accountId: "acc-1",
  status: "ok",
  configuredProxy: true,
  proxyRemoteDns: true,
  sharedWithAccountIds: [],
  warnings: [],
};

describe("egress status chip helpers", () => {
  it("maps canonical primary labels", () => {
    expect(egressPrimaryChipLabel("ok")).toBe("Egress OK");
    expect(egressPrimaryChipLabel("unknown")).toBe("Egress unknown");
    expect(egressPrimaryChipLabel(undefined)).toBe("Egress unknown");
    expect(egressPrimaryChipLabel("direct_egress")).toBe("Direct egress");
    expect(egressPrimaryChipLabel("shared_egress")).toBe("Shared IP");
    expect(egressPrimaryChipLabel("probe_failed")).toBe("Probe failed");
  });

  it("suppresses stale observed IP after probe failure", () => {
    expect(
      shouldShowObservedIp({
        ...baseEgress,
        status: "probe_failed",
        observedIp: "93.184.216.34",
        error: "timeout",
      }),
    ).toBe(false);
  });

  it("builds accessible primary chip titles with observed IP and checked time", () => {
    const title = buildEgressPrimaryChipTitle({
      ...baseEgress,
      observedIp: "8.8.8.8",
      checkedAt: "2026-06-12T12:00:00+00:00",
    });

    expect(title).toContain("Egress OK");
    expect(title).toContain("Observed IP 8.8.8.8");
    expect(title).toContain("Checked");
  });
});

describe("shouldShowAccountListEgressChips", () => {
  it("shows chips when egress summary is missing", () => {
    const account = createAccountSummary({ egress: undefined });
    expect(shouldShowAccountListEgressChips(account)).toBe(true);
  });

  it("hides unknown chips for direct accounts without proxy", () => {
    const account = createAccountSummary({
      egress: {
        accountId: "acc_primary",
        status: "unknown",
        configuredProxy: false,
        sharedWithAccountIds: [],
        warnings: [],
      },
    });
    expect(shouldShowAccountListEgressChips(account)).toBe(false);
  });

  it("shows chips for proxied accounts even when status is unknown", () => {
    const account = createAccountSummary({
      proxy: {
        host: "proxy.example.com",
        port: 1080,
        hasPassword: false,
        remoteDns: true,
      },
      egress: {
        accountId: "acc_primary",
        status: "unknown",
        configuredProxy: true,
        sharedWithAccountIds: [],
        warnings: [],
      },
    });
    expect(shouldShowAccountListEgressChips(account)).toBe(true);
  });
});

describe("EgressStatusChips", () => {
  it("renders primary and warning chips with titles", () => {
    render(
      <EgressStatusChips
        egress={{
          ...baseEgress,
          warnings: ["local_dns_risk"],
        }}
      />,
    );

    const primary = screen.getByTestId("egress-status-badge");
    expect(primary).toHaveTextContent("Egress OK");
    expect(primary).toHaveAttribute("title");

    const warning = screen.getByTestId("egress-warning-chip-local_dns_risk");
    expect(warning).toHaveTextContent("Local DNS risk");
    expect(warning).toHaveAttribute("title", expect.stringContaining("Local DNS"));
  });

  it("wraps chips in a flex container for narrow layouts", () => {
    render(<EgressStatusChips egress={baseEgress} compact />);

    const container = screen.getByTestId("egress-status-chips");
    expect(container).toHaveClass("flex-wrap");
    expect(screen.getByTestId("egress-status-badge")).toHaveClass("text-[10px]");
  });
});
