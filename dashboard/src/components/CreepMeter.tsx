import { cn } from "@/lib/utils"
import { LABELS } from "@/lib/api"

const COLORS = ["", "bg-emerald-500", "bg-lime-500", "bg-amber-400", "bg-orange-500", "bg-rose-500"]

export function CreepMeter({ score, size = "lg" }: { score: number | null; size?: "lg" | "sm" }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className={cn("font-semibold tabular-nums", size === "lg" ? "text-4xl" : "text-2xl")}>{score ?? "?"}/5</span>
        <span className="text-muted-foreground">{score ? LABELS[score] : "Not scored"}</span>
      </div>
      <div className="flex gap-1" role="meter" aria-label="Creep score" aria-valuemin={1} aria-valuemax={5} aria-valuenow={score ?? undefined}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className={cn("h-2.5 flex-1 rounded-full", score && i <= score ? COLORS[score] : "bg-muted")} />
        ))}
      </div>
    </div>
  )
}
