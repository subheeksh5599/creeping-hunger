import { Progress } from "@/components/ui/progress"
import { type EndUserBudget } from "@/lib/api"

export function BudgetMeter({ budget }: { budget: EndUserBudget }) {
  const pct = Math.min(100, (100 * budget.spend_usd) / (budget.limit_usd || 1))
  const resets = budget.resets_at && new Date(budget.resets_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })
  return (
    <div className="flex flex-col gap-2 text-sm">
      <Progress value={pct} aria-label="Per-user budget used" />
      <p>
        <span className="font-medium tabular-nums">${budget.spend_usd.toFixed(4)}</span>
        <span className="text-muted-foreground"> of ${budget.limit_usd.toFixed(2)} used{resets ? `, resets ${resets}` : ""}{budget.blocked ? ", blocked" : ""}</span>
      </p>
    </div>
  )
}
