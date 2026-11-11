import { Progress } from "@/components/ui/progress"
import { LABELS } from "@/lib/api"

export function CreepMeter({ score }: { score: number | null }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="text-4xl font-semibold tabular-nums">{score ?? "?"}/5</span>
        <span className="text-muted-foreground">{score ? LABELS[score] : "Not scored"}</span>
      </div>
      <Progress value={score ? score * 20 : 0} aria-label="Creep score" />
    </div>
  )
}
