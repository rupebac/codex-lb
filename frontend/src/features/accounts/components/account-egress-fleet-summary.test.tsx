import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountEgressFleetSummary } from "@/features/accounts/components/account-egress-fleet-summary";

vi.mock("@/features/accounts/hooks/use-accounts", () => ({
  useAccountEgressReport: vi.fn(),
}));

import { useAccountEgressReport } from "@/features/accounts/hooks/use-accounts";

function renderSummary() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountEgressFleetSummary />
    </QueryClientProvider>,
  );
}

describe("AccountEgressFleetSummary", () => {
  it("renders fleet egress counts from the report query", () => {
    vi.mocked(useAccountEgressReport).mockReturnValue({
      data: {
        accounts: [{ accountId: "a" }],
        unknownCount: 2,
        failedCount: 1,
        directCount: 1,
        sharedIpCount: 2,
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAccountEgressReport>);

    renderSummary();

    expect(screen.getByTestId("egress-fleet-summary")).toBeInTheDocument();
    expect(screen.getByTestId("egress-fleet-unknown")).toHaveTextContent("Unknown 2");
    expect(screen.getByTestId("egress-fleet-failed")).toHaveTextContent("Failed 1");
    expect(screen.getByTestId("egress-fleet-direct")).toHaveTextContent("Direct 1");
    expect(screen.getByTestId("egress-fleet-shared")).toHaveTextContent("Shared IP 2");
  });

  it("shows an all-verified badge when every count is zero", () => {
    vi.mocked(useAccountEgressReport).mockReturnValue({
      data: {
        accounts: [{ accountId: "a" }],
        unknownCount: 0,
        failedCount: 0,
        directCount: 0,
        sharedIpCount: 0,
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAccountEgressReport>);

    renderSummary();

    expect(screen.getByTestId("egress-fleet-ok")).toHaveTextContent("All verified");
  });
});
