import { useEffect, useState, type ReactNode } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { CreepMeter } from "@/components/CreepMeter"
import { Disclaimer } from "@/components/Disclaimer"
import { Nav } from "@/components/Nav"
import { getReview, usd, type DoneEvent, type ResultEvent, type ReviewEvent } from "@/lib/api"

type Side = { id: string; result: ResultEvent; done?: DoneEvent }

function side(id: string, events: ReviewEvent[]): Side | null {
  const result = events.find((e): e is ResultEvent => e.type === "result")
  return result ? { id, result, done: events.find((e): e is DoneEvent => e.type === "done") } : null
}

const yesNo = (v?: string) => <Badge variant={v === "yes" ? "destructive" : v === "no" ? "secondary" : "outline"}>{v ?? "unclear"}</Badge>

const ROWS: [string, (s: Side) => ReactNode][] = [
  ["Sells data", (s) => yesNo(s.result.extraction.sells_data)],
  ["Shares for ads", (s) => yesNo(s.result.extraction.shares_for_ads)],
  ["Trains AI on your data", (s) => yesNo(s.result.extraction.ai_training)],
  ["Sensitive data", (s) => s.result.extraction.sensitive_data?.join(", ") || "none listed"],
  ["Red flags", (s) => s.result.extraction.red_flags?.length ?? 0],
  ["Breaches on record", (s) => s.result.research.breaches?.length ?? 0],
  ["ToS;DR grade", (s) => s.result.research.tosdr_grade ?? "n/a"],
  ["Old Mozilla PNI review", (s) => (s.result.research.pni_found ? `${s.result.research.pni_warning_label ? "had the warning label" : "reviewed"}${s.result.research.pni_stale ? " (stale)" : ""}` : "none archived")],
  ["Minutes to read the policy", (s) => s.result.stats.reading_minutes ?? "n/a"],
  ["Reading grade level", (s) => s.result.stats.fk_grade ?? "n/a"],
  ['"may" per 1,000 words', (s) => s.result.stats.weasel_may_per_1k_words ?? "n/a"],
  ["Judge model", (s) => <span className="font-mono text-xs">{s.result.judge?.model ?? "n/a"}</span>],
  ["Review time", (s) => (s.done ? `${Math.round(s.done.seconds)} s` : "n/a")],
  ["Cost", (s) => usd(s.done?.billed_usd ?? s.done?.total_cost_usd)],
]

export function Compare({ a, b }: { a: string; b: string }) {
  const [sides, setSides] = useState<(Side | null)[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([a, b].map((id) => getReview(id).then((r) => side(id, r.events))))
      .then(setSides)
      .catch((e: Error) => setError(e.message))
  }, [a, b])

  if (error || sides?.some((s) => !s))
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
        <Nav />
        <Alert variant="destructive"><AlertTitle>Could not compare</AlertTitle><AlertDescription>{error ?? "One of these reviews has no verdict."}</AlertDescription></Alert>
      </div>
    )
  if (!sides) return <div className="mx-auto flex max-w-5xl flex-col gap-4 p-6"><Nav /><Skeleton className="h-48" /><Skeleton className="h-96" /></div>

  const pair = sides as Side[]
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <Nav />
      <div className="grid gap-4 md:grid-cols-2">
        {pair.map((s) => (
          <Card key={s.id}>
            <CardHeader>
              <CardDescription>{s.result.brand}</CardDescription>
              <CardTitle className="text-xl"><a className="hover:underline" href={`#/review/${s.id}`}>{s.result.product}</a></CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <CreepMeter score={s.result.score} size="sm" />
              <p className="font-medium">{s.result.headline}</p>
              <div className="flex flex-wrap gap-2">
                {s.result.warning_label && <Badge variant="destructive">*Privacy Not Included</Badge>}
                {s.result.blocked && <Badge variant="destructive">Prompt injection blocked</Badge>}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>Side by side</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow><TableHead /><TableHead>{pair[0].result.product}</TableHead><TableHead>{pair[1].result.product}</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {ROWS.map(([label, cell]) => (
                <TableRow key={label}>
                  <TableCell className="font-medium">{label}</TableCell>
                  <TableCell className="whitespace-normal">{cell(pair[0])}</TableCell>
                  <TableCell className="whitespace-normal">{cell(pair[1])}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Disclaimer />
    </div>
  )
}
