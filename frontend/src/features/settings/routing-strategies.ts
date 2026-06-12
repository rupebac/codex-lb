import type { DashboardSettings } from "@/features/settings/schemas";

export const ROUTING_STRATEGY_OPTIONS: Array<{
  value: DashboardSettings["routingStrategy"];
  label: string;
}> = [
  { value: "capacity_weighted", label: "Capacity weighted" },
  { value: "relative_availability", label: "Relative availability" },
  { value: "fill_first", label: "Fill first" },
  { value: "sequential_drain", label: "Sequential drain" },
  { value: "reset_drain", label: "Reset drain" },
  { value: "single_account", label: "Single account" },
  { value: "usage_weighted", label: "Usage weighted" },
  { value: "round_robin", label: "Round robin" },
];
