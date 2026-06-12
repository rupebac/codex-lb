import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAccountEgressReport } from "@/features/accounts/hooks/use-accounts";

const countChipClassName =
  "h-5 border-border/60 bg-muted/40 px-2 text-[11px] font-medium text-foreground";

export function AccountEgressFleetSummary() {
  const reportQuery = useAccountEgressReport();
  const report = reportQuery.data;

  if (reportQuery.isLoading || reportQuery.isError || !report) {
    return null;
  }

  const total = report.accounts.length;
  if (total === 0) {
    return null;
  }

  const items = [
    { label: "Unknown", count: report.unknownCount, testId: "egress-fleet-unknown" },
    { label: "Failed", count: report.failedCount, testId: "egress-fleet-failed" },
    { label: "Direct", count: report.directCount, testId: "egress-fleet-direct" },
    { label: "Shared IP", count: report.sharedIpCount, testId: "egress-fleet-shared" },
  ].filter((item) => item.count > 0);

  return (
    <section
      aria-label="Fleet egress summary"
      className="flex flex-wrap items-center gap-2 rounded-lg border bg-card px-3 py-2"
      data-testid="egress-fleet-summary"
    >
      <span className="text-xs font-medium text-muted-foreground">Fleet egress</span>
      {items.map((item) => (
        <Badge
          key={item.label}
          variant="outline"
          className={cn(countChipClassName)}
          data-testid={item.testId}
        >
          {item.label} {item.count}
        </Badge>
      ))}
      {items.length === 0 ? (
        <Badge variant="outline" className={cn(countChipClassName)} data-testid="egress-fleet-ok">
          All verified
        </Badge>
      ) : null}
    </section>
  );
}
