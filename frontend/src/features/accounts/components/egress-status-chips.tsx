import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AccountEgressStatus } from "@/features/accounts/schemas";
import {
  buildEgressPrimaryChipTitle,
  egressPrimaryChipClassName,
  egressPrimaryChipLabel,
  egressWarningChipClassName,
  egressWarningChipLabel,
  egressWarningDescription,
  resolveEgressPrimaryStatus,
} from "@/features/accounts/components/egress-status-chip-utils";

export type EgressStatusChipsProps = {
  egress: AccountEgressStatus | null | undefined;
  compact?: boolean;
  className?: string;
  primaryTestId?: string;
};

export function EgressStatusChips({
  egress,
  compact = false,
  className,
  primaryTestId = "egress-status-badge",
}: EgressStatusChipsProps) {
  const status = resolveEgressPrimaryStatus(egress);
  const chipSize = compact ? "h-4 px-1.5 text-[10px]" : "h-5 px-2 text-[11px]";

  return (
    <div
      className={cn("flex flex-wrap items-center gap-1", className)}
      data-testid="egress-status-chips"
    >
      <Badge
        variant="outline"
        className={cn("font-medium", chipSize, egressPrimaryChipClassName(status))}
        title={buildEgressPrimaryChipTitle(egress)}
        data-testid={primaryTestId}
      >
        {egressPrimaryChipLabel(status)}
      </Badge>
      {egress?.warnings?.map((warning) => (
        <Badge
          key={warning}
          variant="outline"
          className={cn("font-medium", chipSize, egressWarningChipClassName)}
          title={egressWarningDescription(warning)}
          data-testid={`egress-warning-chip-${warning}`}
        >
          {egressWarningChipLabel(warning)}
        </Badge>
      ))}
    </div>
  );
}
