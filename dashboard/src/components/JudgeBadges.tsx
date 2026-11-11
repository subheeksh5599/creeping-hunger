import { Badge } from "@/components/ui/badge"
import { type Judge } from "@/lib/api"

export function JudgeBadges({ judge }: { judge: Judge }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-muted-foreground">Verdict by</span>
      <Badge variant="secondary" className="font-mono">{judge.model}</Badge>
      {judge.policy && <Badge variant="outline">routing policy {judge.policy}</Badge>}
      <Badge variant={judge.fallback_used ? "destructive" : "outline"}>{judge.fallback_used ? "fallback model answered" : "primary model answered"}</Badge>
      {judge.attempts && Number(judge.attempts) > 1 && <Badge variant="outline">{judge.attempts} attempts</Badge>}
    </div>
  )
}
