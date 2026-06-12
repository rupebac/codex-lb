import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountCards } from "@/features/dashboard/components/account-cards";
import { createAccountSummary } from "@/test/mocks/factories";

describe("AccountCards", () => {
  it("renders every account at once without capping height or scrolling", () => {
    render(
      <AccountCards
        accounts={Array.from({ length: 18 }, (_, index) =>
          createAccountSummary({
            accountId: `acc-${index + 1}`,
            email: `account-${index + 1}@example.com`,
            displayName: `Account ${index + 1}`,
          }),
        )}
        onAction={vi.fn()}
      />,
    );

    const grid = screen.getByTestId("dashboard-account-cards");
    // Every account is mounted (no virtualisation / no clipping window).
    for (let index = 1; index <= 18; index += 1) {
      expect(screen.getByText(`Account ${index}`)).toBeInTheDocument();
    }
    // The grid must not impose a scroll cap on the accounts section.
    expect(grid).not.toHaveClass("overflow-y-auto");
    expect(grid.style.maxHeight).toBe("");
  });

  it("gives each warm-up toggle a descriptive account-specific name", () => {
    render(
      <AccountCards
        accounts={[
          createAccountSummary({
            accountId: "acc-1",
            email: "one@example.com",
            displayName: "One Account",
            limitWarmupEnabled: false,
          }),
          createAccountSummary({
            accountId: "acc-2",
            email: "two@example.com",
            displayName: "Two Account",
            limitWarmupEnabled: true,
          }),
        ]}
        onAction={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Enable limit warm-up for One Account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable limit warm-up for Two Account" })).toBeInTheDocument();
  });
});
