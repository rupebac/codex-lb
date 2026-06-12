import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountProxySection } from "@/features/accounts/components/account-proxy-section";
import type { AccountSummary } from "@/features/accounts/schemas";

const baseAccount: AccountSummary = {
  accountId: "acc-1",
  email: "user@example.com",
  displayName: "user@example.com",
  planType: "plus",
  status: "active",
  additionalQuotas: [],
  limitWarmupEnabled: false,
};

vi.mock("@/features/accounts/hooks/use-accounts", () => ({
  useClearAccountProxy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProbeAccountEgress: () => ({ mutate: vi.fn(), isPending: false }),
}));

function renderSection(account: AccountSummary) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountProxySection account={account} />
    </QueryClientProvider>,
  );
}

describe("AccountProxySection egress UI", () => {
  it("shows egress status badge and observed IP", () => {
    renderSection({
      ...baseAccount,
      egress: {
        accountId: "acc-1",
        status: "direct_egress",
        observedIp: "93.184.216.34",
        checkedAt: "2026-06-12T12:00:00+00:00",
        configuredProxy: false,
        proxyRemoteDns: true,
        sharedWithAccountIds: [],
        warnings: [],
      },
    });

    expect(screen.getByTestId("egress-status-badge")).toHaveTextContent("Direct egress");
    expect(screen.getByTestId("egress-observed-ip")).toHaveTextContent("93.184.216.34");
    expect(screen.getByTestId("egress-probe-button")).toBeInTheDocument();
  });

  it("renders local DNS risk warning", () => {
    renderSection({
      ...baseAccount,
      proxy: {
        host: "proxy.example.com",
        port: 1080,
        hasPassword: false,
        remoteDns: false,
      },
      egress: {
        accountId: "acc-1",
        status: "ok",
        observedIp: "8.8.8.8",
        configuredProxy: true,
        proxyRemoteDns: false,
        sharedWithAccountIds: [],
        warnings: ["local_dns_risk"],
      },
    });

    expect(screen.getByTestId("egress-warnings")).toHaveTextContent("Local DNS resolution");
  });
});
